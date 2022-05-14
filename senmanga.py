#!/usr/bin/env python3
# coding: utf-8

import lxml.etree
import sys
import codecs
import re
import time
import os
import zipfile
import getopt
import shutil
from http.cookies import SimpleCookie
from requests import session, exceptions
from threading import Thread, Lock, Event
from time import sleep
import pathlib
import subprocess
import hashlib
import datetime

# zipファイルを作成する作業ディレクトリ
EXT = '/tmp/'

#
# senmangaクラス
#


class SenManga:
    # コンストラクタ
    def __init__(self, url, path, max):
        # urlが最後/で終わる場合、/を取り除く
        self.__url = re.sub(r'/$', '', url)
        self.threadcount = 0
        self.Maxthread = max
        self.lock = Lock()
        self.threadready = Event()
        self.path = path

    # スレッドの待ち合わせ
    def Wait_for_threads(self):
        while self.threadcount:
            self.threadready.wait()
            self.threadready.clear()

    # ダウンロード
    def download(self):
        list = re.search(r'https*://[^/]+/([^/]+)/([^/]+)', self.__url)
        tags = []

        if list is not None:
            # 「https://raw.senmanga.com/Dragon-Age/2020-07」の形式ならばそのままイメージ取得
            urls = [list[0]]
        else:
            list = re.search(r'https*://[^/]+/([^/]+)', self.__url)
            if list is not None:
                # 「https://raw.senmanga.com/Dragon-Age」の形式ならばそのままリストを取得、各リストに対しダウンロードを実行
                # 「https://raw.senmanga.com/Dragon-Age/2020-07」の形式のリストを取得
                urls, tags = self.getURLlist(list[0])
                if urls is None:
                    return
            else:
                # ダウンロードできるURLでないため終了
                return

        # print(urls)

        for url in urls:
            # ファイルを展開するパスを作成 (最後に / を含む)
            list = re.search(r'https*://[^/]+/([^/]+)/([^/]+)', url)
            try:
                chapter = '%04d' % int(list.group(2))
            except ValueError:
                try:
                    chapter = '%06.1f' % float(list.group(2))
                except ValueError:
                    chapter = list.group(2)

            basedir = self.path + '/' + chapter

            if os.path.isfile(basedir + '.zip'):
                #print('すでに存在:', url)
                stat = os.stat(basedir + '.zip')
                if stat.st_size == 0 and time.time() - stat.st_mtime > 7 * 24 * 3600:
                    # ファイルサイズが0、かつ、最終更新日が7日より過去
                    print(basedir + '.zip is size zero and older than 7days')
                else:
                    continue

            pagesize, status = self.getpagesize(url)
            if pagesize is None:
                print('pagesizeの取得に失敗しました', url)

                # HTTPステータスが200以外で返ってきた場合、空ファイルを作成、または、最終更新日を更新する
                if status is not None:
                    with open(basedir + '.zip', 'wb') as f:
                        pass
                    
                continue

            try:
                os.makedirs(self.path)
            except FileExistsError:
                pass

            # 作業ディレクトリの作成
            try:
                os.makedirs(EXT + basedir)
            except FileExistsError:
                shutil.rmtree(EXT + basedir)
                os.makedirs(EXT + basedir)

            # イメージダウンロード実行
            self.getimage(url, EXT + basedir + '/', chapter, pagesize)
            self.Wait_for_threads()

            # zipファイルの作成
            count = 0
            for x in os.listdir(EXT + basedir):
                if (re.match(r'.*\.(jpg|jpeg|png|JPG|JPEG|PNG)', x) and os.path.isfile(os.path.join(EXT + basedir, x))):
                    count = count + 1

            if count == 0:
                # イメージファイルが存在しない場合、0byteのファイルを作成する
                with open(basedir + '.zip', 'wb') as f:
                    pass
            else:
                # ダウンロードしたイメージをzipファイルにまとめる
                with zipfile.ZipFile(basedir + '.zip', 'w', compression=zipfile.ZIP_STORED) as new_zip:
                    for x in sorted(os.listdir(EXT + basedir)):
                        if (re.match(r'.*\.(jpg|jpeg|png|JPG|JPEG|PNG)', x) and
                                os.path.isfile(os.path.join(EXT + basedir, x))):
                            new_zip.write(os.path.join(EXT + basedir, x), arcname=x)

            shutil.rmtree(EXT + basedir)

        # タグ情報の空ファイルを作成する。すでに存在する場合はスキップ
        for tag in tags:
            tag_file = self.path + '/' + tag + '.info'
            if not os.path.isfile(tag_file):
                with open(tag_file, 'wb') as f:
                    pass                

        return

    def getURLlist(self, url):
        req = session()
        req.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
            'Authority': 'raw.senmanga.com',
            'Referer': url,
        }

        for retry in range(0, 10):
            try:
                # HTML情報取得
                response = req.get(url)
                #print('url:' + url, 'status_code:' + str(response.status_code))

                if response.status_code == 200:
                    # 取得HTMLパース
                    html = lxml.etree.HTML(response.text)

                    # チャプターリストを取得
                    # //ul[@class="chapter-list"]/li/a/@href
                    list = html.xpath('//ul[@class="chapter-list"]/li/a/@href')

                    # Genres:情報を取得
                    # /html/body/div[3]/div/div[1]/div[1]/div[2]/div[2]/div[3]/div[1]/strong
                    # /html/body/div[3]/div/div[1]/div[1]/div[2]/div[2]/div[@class="info"]/div[1]/a/text()
                    item = html.xpath('/html/body/div[3]/div/div[1]/div[1]/div[2]/div[2]/div[@class="info"]/div[1]/strong/text()')
                    if len(item) > 0 and item[0] == 'Genres:':
                        tags = html.xpath('/html/body/div[3]/div/div[1]/div[1]/div[2]/div[2]/div[@class="info"]/div[1]/a/text()')
                    else:
                        tags = []

                    return list, tags
                else:
                    print('Status Error ' + str(response.status_code) + ':' + url)
                    return None, None

            except exceptions.ConnectionError:
                print('ConnectionError:' + url)
            except exceptions.Timeout:
                print('Timeout:' + url)

            # リトライ前に2秒待つ
            sleep(2)

        return None, None

    # 接続、クッキー・ページリストを取得
    def getpagesize(self, url):
        req = session()
        req.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
            'Authority': 'raw.senmanga.com',
            'Referer': url,
        }

        # HTML情報取得
        for retry in range(0, 10):
            try:
                response = req.get(url + '/1')
                print('url:' + url + '/1')

                if response.status_code == 200:
                    # 取得HTMLパース
                    index = lxml.etree.HTML(response.text)

                    # イメージページ数取得
                    # /html/body/div[3]/div[3]/span/select/option[1]
                    pagelist = index.xpath('//span[@class="page-list"]/select[@name="page"]/option')

                    # イメージページ数箇所取得
                    # /html/body/div[3]/div[3]/span/select
                    pagelists = index.xpath('//span[@class="page-list"]/select[@name="page"]')

                    # イメージページ数を返す
                    return int(len(pagelist)/len(pagelists)), None

                print('url:' + url + '/1', 'status_code:' + str(response.status_code))
                return None, str(response.status_code)

            except exceptions.ConnectionError:
                print('ConnectionError:' + url)
            except exceptions.Timeout:
                print('Timeout:' + url)

            # リトライ前に2秒待つ
            sleep(2)

        return None, None

    #
    def getimage(self, url, basedir, chapter, pagesize):
        self.__imgreq = session()
        self.__imgreq.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3',
            'Accept-Encoding': 'gzip',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
            'Authority': 'raw.senmanga.com',
            'Referer': url,
        }

        for page in range(1, pagesize + 1):
            if self.threadcount == self.Maxthread:
                self.threadready.wait()

            thread = Thread(target=self.downloadImage, args=(url, basedir, chapter, page))
            thread.start()
            self.threadready.clear()
            # self.downloadImage(url, basedir, chapter, page)

    # イメージファイルのダウンロード
    def downloadImage(self, url, basedir, chapter, page):
        imgurl = url.replace('raw.senmanga.com', 'raw.senmanga.com/viewer') + '/' + str(page)
        filename = basedir + chapter + '_' + '%03d' % page + '.jpeg'
        wk_filename = basedir + chapter + '_' + '%03d' % page + '.work'

        self.lock.acquire()
        self.threadcount += 1
        self.lock.release()

        for retry in range(0, 10):
            try:
                r = self.__imgreq.get(imgurl, stream=True, timeout=(10.0, 10.0))

                # ハッシュオブジェクトを作ります
                h = hashlib.new('md5')
                hash = ''

                if r.status_code == 200:
                    with open(wk_filename, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=4096):
                            if chunk:  # filter out keep-alive new chunks
                                h.update(chunk)
                                f.write(chunk)
                                f.flush()
                        f.close()

                    hash = h.hexdigest()

                    # 2f0f6c4f7efbee0a720ece0e906c7fda Sorry, this page is not available
                    if (hash != '2f0f6c4f7efbee0a720ece0e906c7fda'):
                        self.lock.acquire()
                        self.threadcount -= 1
                        self.lock.release()
                        self.threadready.set()

                        os.rename(wk_filename, filename)
                        print('image file=' + filename, '  url:' + imgurl)
                        return

                if r.status_code == 500 or hash == '2f0f6c4f7efbee0a720ece0e906c7fda':
                    imgurl = url + '/' + str(page)
                    r = self.__imgreq.get(imgurl, stream=True)
                    if r.status_code == 200:
                        # 取得HTMLパース
                        html = lxml.etree.HTML(r.content)
                        # /html/body/div[5]/a/img
                        states = html.xpath('//img[@class="picture"]/@src')
                        imgurl = ''.join(states[0].splitlines())

                        # イメージファイル名が「/1-61ffbc68eddac.jpg」のような形式の時、1をページ番号として処理する
                        num = re.match(r'^.*/(\d+)-[^/]*$', imgurl)
                        if num:
                            page = int(num.group(1))
                            fmt = re.match(r'^.*\.png$', imgurl)
                            if fmt:
                                filename = basedir + chapter + '_' + '%03d' % page + '.png'
                            else:
                                filename = basedir + chapter + '_' + '%03d' % page + '.jpeg'

                        continue

                self.lock.acquire()
                self.threadcount -= 1
                self.lock.release()
                self.threadready.set()

                print('url:' + imgurl, 'status_code:' + str(r.status_code))
                return

            except exceptions.ConnectionError:
                print('ConnectionError:' + imgurl)
            except exceptions.ReadTimeout:
                print('ReadTimeout:' + imgurl)
            except exceptions.Timeout:
                print('Timeout:' + imgurl)
            except Exception as e:
                print(e)
                break

            # リトライ前に2秒待つ
            sleep(2)

        self.lock.acquire()
        self.threadcount -= 1
        self.lock.release()
        self.threadready.set()

        # リトライ回数をオーバーで終了
        print('Retry over:' + imgurl)
        return

#
# ファイル名に使用できない、使用しない方がいい文字を削除
#


def cleanPath(path):
    path = path.strip()  # 文字列の前後の空白を削除
    path = path.replace('|', '')
    path = path.replace(':', '')
    path = path.replace('/', '')
    return path

#
# メイン
#


if __name__ == '__main__':
    if len(sys.argv) > 2:
        url = sys.argv[1]
        path = sys.argv[2]

        print(url, path)
        sen = SenManga(url, path, 4)
        sen.download()
