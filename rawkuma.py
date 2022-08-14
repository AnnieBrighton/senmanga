#!/usr/bin/env python3
#

import lxml.etree
import sys
import re
import time
import os
import zipfile
import shutil
from requests import session, exceptions
from threading import Thread, Lock, Event
from time import sleep
import traceback

# zipファイルを作成する作業ディレクトリ
EXT = '/tmp/'

#
# senmangaクラス
#

class RawKuma:
    # コンストラクタ
    def __init__(self, url, path, max):
        # urlが最後/で終わる場合、/を取り除く
        self.__url = re.sub(r'/$', '', url)
        self.threadcount = 0
        self.Maxthread = max
        self.lock = Lock()
        self.threadready = Event()
        self.path = path

        self.__imgreq = session()
        self.__imgreq.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3',
            'Accept-Encoding': 'gzip',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
        }


    # スレッドの待ち合わせ
    def Wait_for_threads(self):
        while self.threadcount:
            self.threadready.wait()
            self.threadready.clear()

    # イメージファイルのダウンロード
    def downloadImage(self, imgurl, basedir, chapter, page):
        filename = basedir + chapter + '_' + '%03d' % page + '.jpeg'

        self.lock.acquire()
        self.threadcount += 1
        self.lock.release()

        for _ in range(0, 10):
            try:
                r = self.__imgreq.get(imgurl, stream=True, timeout=(10.0, 10.0))

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

                print('image file=' + filename, '  url:' + imgurl, '   status_code:' + str(r.status_code))
                return

            except exceptions.ConnectionError:
                print('ConnectionError:' + imgurl)
            except exceptions.ReadTimeout:
                print('ReadTimeout:' + imgurl)
            except exceptions.Timeout:
                print('Timeout:' + imgurl)
            except Exception as e:
                print(e)
                print(traceback.format_exc())
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
    def getimage(self, imgurls, basedir, chapter):

        for page, url in enumerate(imgurls):
            if self.threadcount == self.Maxthread:
                self.threadready.wait()

            thread = Thread(target=self.downloadImage, args=(url, basedir, chapter, page + 1))
            thread.start()
            self.threadready.clear()


    #
    def getImageList(self, url):
        req = session()
        req.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3',
            'Accept-Encoding': 'gzip',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
        }

        for _ in range(0, 10):
            try:
                # HTML情報取得
                response = req.get(url)

                if response.status_code == 200:
                    # 取得HTMLパース
                    html = lxml.etree.HTML(response.text)

                    # イメージリストを取得
                    # <img class="ts-main-image curdown" data-index="0" src="https://kumacdn.club/images/s/spy-x-family/chapter-62-3/1-6281c0b1e24d0.jpg" #      data-server="Server1" onload="ts_reader_control.singleImageOnload();" onerror="ts_reader_control.imageOnError();">
                    # //*[@id="readerarea"]/img[1]
                    # //*[@id="readerarea"]/img
                    srcs = html.xpath('//*[@id="readerarea"]/noscript/p/img/@src')

                    # print('srcs:', srcs)

                    return srcs
                else:
                    print('Status Error ' + str(response.status_code) + ':' + url)
                    return None

            except exceptions.ConnectionError:
                print('ConnectionError:' + url)
            except exceptions.Timeout:
                print('Timeout:' + url)
            except Exception as e:
                print(e)
                print(traceback.format_exc())
                return None

            # リトライ前に2秒待つ
            sleep(2)

        return None


    # URLリストを取得
    def getURLlist(self, url):
        req = session()
        req.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml',
            'Accept-Encoding': 'gzip',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
        }

        for _ in range(0, 10):
            try:
                # HTML情報取得
                response = req.get(url)

                if response.status_code == 200:
                    # 取得HTMLパース
                    html = lxml.etree.HTML(response.text)

                    # チャプターリストを取得
                    # //*[@id="chapterlist"]/ul/li/div/div[1]/a
                    # //*[@id="chapterlist"]/ul/li/div/div[@class="eph-num"]/a
                    lists = html.xpath('//*[@id="chapterlist"]/ul/li/div/div[@class="eph-num"]/a/@href')

                    # Genres:情報を取得
                    # //*[@id="post-920"]/div[2]/div[1]/div[2]/div[8]/span/a
                    # //*[@id="post-920"]/div[2]/div[1]/div[2]/div[@class="wd-full"]/span/a/text()
                    # //*[@id="post-5342"]/div[2]/div[1]/div[2]/div[7]/span/a[1]
                    # //*div[@id="content"]/div/div[@class="postbody"]/article/div[2]/div[1]/div[2]/div[@class="wd-full"]/span/a
                    tags = html.xpath('//*[@class="infox"]/div[@class="wd-full"]/span[@class="mgen"]/a/text()')

                    # Status:情報取得
                    # //*[@id="post-95777"]/div[2]/div[1]/div[1]/div[2]/div[4]/div[1]
                    # //*div[@class="thumbook"]/div[@class="rt"]/div[@class="tsinfo"]/div[@class="imptdt"]/div[1]
                    status = html.xpath('//div[@class="thumbook"]/div[@class="rt"]/div[@class="tsinfo"]/div[1]/text()')
                    text = html.xpath('//div[@class="thumbook"]/div[@class="rt"]/div[@class="tsinfo"]/div[1]/i/text()')
                    if status == [' Status '] and text == ['Completed']:
                        with open('rawkuma-status.txt', 'a') as f:
                            f.write('status: ' + url + '\tCompleted\n')                        

                    return lists, tags
                else:
                    print('Status Error ' + str(response.status_code) + ':' + url)
                    return None, None

            except exceptions.ConnectionError:
                print('ConnectionError:' + url)
            except exceptions.Timeout:
                print('Timeout:' + url)
            except Exception as e:
                print(e)
                print(traceback.format_exc())
                return None, None

            # リトライ前に2秒待つ
            sleep(2)

        return None, None

    # ダウンロード
    def download(self):
        """ 
        """
        tags = []

        list = re.search(r'^(https?://[^/]+/[^/]+)/?$', self.__url)
        if list is not None:
            # 「https://rawkuma.com/bakemonogatari-chapter-1/」の形式ならばそのままイメージ取得
            urls = [list[0] + '/']
        else:
            # 「https://rawkuma.com/manga/bakemonogatari/」の形式ならば、
            list = re.search(r'^(https?://[^/]+/[^/]+/[^/]+)/?$', self.__url)
            if list is not None:
                # 「https://rawkuma.com/manga/bakemonogatari/」の形式ならばそのままリストを取得、各リストに対しダウンロードを実行
                # 「https://rawkuma.com/bakemonogatari-chapter-1/」の形式のリストを取得
                urls, tags = self.getURLlist(list[0])
                if urls is None:
                    print('URL取得エラー:%s' % self.__url)
                    return
            else:
                # ダウンロードできるURLでないため終了
                print('URL形式エラー:%s' % self.__url)
                return

        #print('urls:', urls)
        #print('tags:', tags)

        for url in urls:
            # ファイルを展開するパスを作成 (最後に / を含む)
            list = re.search(r'^https?://[^/]+/[^/]+-chapter-([0-9]+)-([0-9]+)/$', url)
            if list:
                chapter = '%04d.%d' % (int(list.group(1)), int(list.group(2)))
            else:
                list = re.search(r'^https?://[^/]+/[^/]+-chapter-([0-9]+)/$', url)
                if list:
                    chapter = '%04d' % int(list.group(1))
                else:
                    continue

            basedir = self.path + '/' + chapter

            if os.path.isfile(basedir + '.zip'):
                #print('すでに存在:', url)
                stat = os.stat(basedir + '.zip')
                if stat.st_size == 0 and time.time() - stat.st_mtime > 7 * 24 * 3600:
                    # ファイルサイズが0、かつ、最終更新日が7日より過去
                    print(basedir + '.zip is size zero and older than 7days')
                else:
                    continue

            imgurls = self.getImageList(url)
            if imgurls is None:
                print('イメージリストの取得に失敗しました', url)

                # イメージリストの取得に失敗した場合、空ファイルを作成、または、最終更新日を更新する
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
            self.getimage(imgurls, EXT + basedir + '/', chapter)
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
            if tag != 'N/A' and not os.path.isfile(tag_file):
                with open(tag_file, 'wb') as f:
                    pass                

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
        kuma = RawKuma(url, path, 4)
        kuma.download()
