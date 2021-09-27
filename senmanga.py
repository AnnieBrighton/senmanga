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
import subprocess
import hashlib

# zipファイルを作成する作業ディレクトリ
TMPPATH = 'img/'
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
        if path is not None:
            self.path = path
        else:
            self.path = re.search(r'https*://[^/]+/([^/]+)', url).group(1)

    # スレッドの待ち合わせ
    def Wait_for_threads(self):
        while self.threadcount:
            self.threadready.wait()
            self.threadready.clear()

    # ダウンロード
    def download(self):
        list = re.search(r'https*://[^/]+/([^/]+)/([^/]+)', self.__url)
        if list is not None:
            # 「https://raw.senmanga.com/Dragon-Age/2020-07」の形式ならばそのままイメージ取得
            urls = [list[0]]
        else:
            list = re.search(r'https*://[^/]+/([^/]+)', self.__url)
            if list is not None:
                # 「https://raw.senmanga.com/Dragon-Age」の形式ならばそのままリストを取得、各リストに対しダウンロードを実行
                # 「https://raw.senmanga.com/Dragon-Age/2020-07」の形式のリストを取得
                urls = self.getURLlist(list[0])
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

            basedir = TMPPATH + self.path + '/' + chapter

            if os.path.isfile(basedir + '.zip'):
                #print('すでに存在:', url)
                continue

            pagesize = self.getpagesize(url)
            if pagesize is None:
                print('pagesizeの取得に失敗しました', url)
                continue

            try:
                os.makedirs(TMPPATH + self.path)
            except FileExistsError:
                pass

            try:
                os.makedirs(EXT + basedir)
            except FileExistsError:
                shutil.rmtree(EXT + basedir)
                os.makedirs(EXT + basedir)

            # イメージダウンロード実行
            self.getimage(url, EXT + basedir + '/', chapter, pagesize)
            self.Wait_for_threads()

            # ダウンロードしたイメージをzipファイルにまとめる
            with zipfile.ZipFile(basedir + '.zip', 'w', compression=zipfile.ZIP_STORED) as new_zip:
                for x in sorted(os.listdir(EXT + basedir)):
                    if (re.match(r'.*\.(jpg|jpeg|png|JPG|JPEG|PNG)', x) and
                            os.path.isfile(EXT + basedir + '/' + x)):
                        new_zip.write(EXT + basedir + '/' + x, arcname=x)

            shutil.rmtree(EXT + basedir)

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
                    return list
                else:
                    print('Status Error ' + str(response.status_code) + ':' + url)
                    return None

            except exceptions.ConnectionError:
                print('ConnectionError:' + url)
            except exceptions.Timeout:
                print('Timeout:' + url)

            # リトライ前に2秒待つ
            sleep(2)

        return None

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
                    return int(len(pagelist)/len(pagelists))

                print('url:' + url + '/1', 'status_code:' + str(response.status_code))

            except exceptions.ConnectionError:
                print('ConnectionError:' + url)
            except exceptions.Timeout:
                print('Timeout:' + url)

            # リトライ前に2秒待つ
            sleep(2)

        return None

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
                    with open(filename, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=4096):
                            if chunk:  # filter out keep-alive new chunks
                                h.update(chunk)
                                f.write(chunk)
                                f.flush()
                        f.close()

                    hash = h.hexdigest()

                    if (hash != '2f0f6c4f7efbee0a720ece0e906c7fda'):
                        self.lock.acquire()
                        self.threadcount -= 1
                        self.lock.release()
                        self.threadready.set()

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

                        continue

                self.lock.acquire()
                self.threadcount -= 1
                self.lock.release()
                self.threadready.set()

                print('url:' + imgurl, 'status_code:' + str(r.status_code))
                return

            except exceptions.ConnectionError:
                print('ConnectionError:' + imgurl)
            except exceptions.Timeout:
                print('Timeout:' + imgurl)
            except exceptions.ReadTimeout:
                print('ReadTimeout:' + imgurl)

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
    url = sys.argv[1]
    path = None
    if len(sys.argv) > 1:
        path = sys.argv[2]

    print(url, path)
    sen = SenManga(url, path, 4)
    sen.download()
