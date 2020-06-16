#!/usr/bin/env python3
# coding: utf-8

import requests
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
from requests.cookies import cookiejar_from_dict
from time import sleep
import subprocess
import threading


# ファイルをダウンロードし、zipファイルを作成する作業ディレクトリ
TMPPATH = 'img/'

#
# senmangaクラス
#


class SenManga:
    # コンストラクタ
    def __init__(self, url):
        # urlが最後/で終わる場合、/を取り除く
        self.__url = re.sub(r'/$', '', url)
        self.threadcount = 0
        self.Maxthread = 20
        self.lock = threading.Lock()
        self.threadready = threading.Event()

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
            else:
                # ダウンロードできるURLでないため終了
                return

        print(urls)

        for url in urls:
            # ファイルを展開するパスを作成 (最後に / を含む)
            list = re.search(r'https*://[^/]+/([^/]+)/([^/]+)', url)
            title = list.group(1)
            try:
                chapter = '%04d' % int(list.group(2))
            except ValueError:
                try:
                    chapter = '%06.1f' % float(list.group(2))
                except ValueError:
                    chapter = list.group(2)

            basedir = TMPPATH + title + '/' + chapter

            pagesize = self.getpagesize(url)
            if pagesize is None:
                continue

            try:
                EXT = '.download'
                os.makedirs(basedir)
                if os.path.isdir(basedir + EXT):
                    shutil.rmtree(basedir + EXT)
                os.rename(basedir, basedir + EXT)

                # イメージダウンロード実行
                self.getimage(url, basedir + EXT + '/', chapter, pagesize)
                self.Wait_for_threads()

                os.rename(basedir + EXT, basedir)
            except FileExistsError:
                # すでに存在すれば、処理を行わない。
                print('すでに存在:', url)

        return

    def getURLlist(self, url):
        req = requests.session()
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
                print('url:' + url, 'status_code:' + str(response.status_code))

                if response.status_code == 200:
                    # 取得HTMLパース
                    html = lxml.etree.HTML(response.text)

                    # //*[@id="content"]/div[3]/div[2]/div[2]/div[1]/a
                    list = html.xpath('//*[@id="content"]/div[3]/div[@class="group"]/div[@class="element"]/div[@class="title"]/a/@href')
                    return list

            except requests.exceptions.ConnectionError:
                print('ConnectionError:' + url)
            except requests.exceptions.Timeout:
                print('Timeout:' + url)

            # リトライ前に2秒待つ
            sleep(2)

        return None

    # 接続、クッキー・ページリストを取得
    def getpagesize(self, url):
        req = requests.session()
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
                    # /html/body/article/div[1]/div[3]/span/select
                    pagelist = index.xpath('//div[1]/div[3]/span/select[@name="page"]/option')

                    # イメージダウンロード実行
                    return len(pagelist)

                print('url:' + url + '/1', 'status_code:' + str(response.status_code))

            except requests.exceptions.ConnectionError:
                print('ConnectionError:' + url)
            except requests.exceptions.Timeout:
                print('Timeout:' + url)

            # リトライ前に2秒待つ
            sleep(2)

        return None

    #
    def getimage(self, url, basedir, chapter, pagesize):
        self.__imgreq = requests.session()
        self.__imgreq.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
            'Authority': 'raw.senmanga.com',
            'Referer': url,
        }

        for page in range(1, pagesize + 1):
            if self.threadcount == self.Maxthread:
                self.threadready.wait()

            thread = threading.Thread(target=self.downloadImage, args=(url, basedir, chapter, page))
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
                print('image file=' + filename, '  url:' + imgurl)

                if r.status_code == 200:
                    with open(filename, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=4096):
                            if chunk:  # filter out keep-alive new chunks
                                f.write(chunk)
                                f.flush()
                        f.close()

                    self.lock.acquire()
                    self.threadcount -= 1
                    self.lock.release()
                    self.threadready.set()
                    return

                print('url:' + imgurl, 'status_code:' + str(r.status_code))

            except requests.exceptions.ConnectionError:
                print('ConnectionError:' + imgurl)
            except requests.exceptions.Timeout:
                print('Timeout:' + imgurl)
            except requests.exceptions.ReadTimeout:
                print('ReadTimeout:' + imgurl)

            # リトライ前に2秒待つ
            sleep(2)

        # リトライ回数をオーバーで終了
        print('Retry over:' + imgurl)

        self.lock.acquire()
        self.threadcount -= 1
        self.lock.release()
        self.threadready.set()
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
    for url in sys.argv[1:]:
        sen = SenManga(url)
        sen.download()
