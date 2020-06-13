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
import subprocess

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
        self.__imageurl = ''

    # 接続、クッキー・ページリストを取得
    def gethtml(self):
        self.__req = requests.session()
        self.__req.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
            'Authority': 'raw.senmanga.com',
            'Referer': self.__url,
        }

        # HTML情報取得
        print('url:' + self.__url + '/1')
        self.__response = self.__req.get(self.__url + '/1')
        print('status_code:' + str(self.__response.status_code))

        self.__imageurl = self.__url.replace('raw.senmanga.com', 'raw.senmanga.com/viewer') + '/'

        # 取得HTMLパース
        self.__index = lxml.etree.HTML(self.__response.text)

        # イメージ取得用URL情報取得
        # /html/body/article/div[1]/div[3]/span/select
        list = self.__index.xpath('//div[1]/div[3]/span/select[@name="page"]/option')
        print(len(list))
        self.__pagesize = len(list)
        # list = self.__index.xpath('//div[@id="chapter-navigation"]/a/@href')
        # self.__pagesize = int(re.search(r'/([0-9]*)$', list[1]).group(1))

    #
    def getimage(self):
        self.__imgreq = requests.session()
        self.__imgreq.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
            'Authority': 'raw.senmanga.com',
            'Referer': self.__url,
        }

        # ファイルを展開するパスを作成 (最後に / を含む)
        basedir = TMPPATH + re.search(r'https*://[^/]+/([^/]+/[^/]+)', self.__url).group(1) + '/'

        try:
            os.makedirs(basedir)
        except FileExistsError:
            pass

        for page in range(1, self.__pagesize + 1):
            self.downloadImage(basedir, page)

    # イメージファイルのダウンロード
    def downloadImage(self, basedir, page):
        imgurl = self.__imageurl + str(page)
        filename = basedir + '%04d' % page + '.jpeg'
        print("Download Image File=" + filename)

        for retry in range(0, 10):
            try:
                print('url:' + imgurl)
                r = self.__imgreq.get(imgurl, stream=True, timeout=(10.0, 10.0))
                print('status_code:' + str(r.status_code))

                with open(filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=4096):
                        if chunk:  # filter out keep-alive new chunks
                            f.write(chunk)
                            f.flush()
                    f.close()

                return filename

            except requests.exceptions.ConnectionError:
                print('ConnectionError:' + imgurl)
                continue
            except requests.exceptions.Timeout:
                print('Timeout:' + imgurl)
                continue
            except requests.exceptions.ReadTimeout:
                print('Timeout:' + imgurl)
                continue

        # リトライ回数をオーバーで終了
        print('Retry over:' + imgurl)
        sys.exit()

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
        sen.gethtml()
        sen.getimage()
