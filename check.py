#!/usr/bin/env python3
# coding: utf-8

import os, sys
import glob
from requests import session, exceptions
from lxml import etree
import re
from time import sleep
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

class SenMangaCheck:
    def __init__(self, url, path) -> None:
        self.url = url
        self.path = path
        pass

    def get_fileList(self):
        ids = {}
        files = glob.glob(self.path + '/**/*.url', recursive=True)

        for file in files:
            ids[os.path.splitext(os.path.basename(file))[0]] = file

        return ids

    def get_urlList(self):
        req = session()
        req.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
            'Authority': 'raw.senmanga.com',
            'Referer': self.url,
        }

        for _ in range(0, 10):
            try:
                # HTML情報取得
                response = req.get(self.url)

                if response.status_code == 200:
                    # 取得HTMLパース
                    html = etree.HTML(response.text)

                    # //div[@class="listupd"]/div[@class="mng"]/div[@class="dtl"]/a[@class="series"]/@href
                    #lists = html.xpath('//div[@class="listupd"]/div[@class="mng"]/div[@class="dtl"]/a[@class="series"]/@href')

                    ids = {}
                    #for url in lists:
                    #    ids[re.sub(r'^https?://[^/]+/', '', url)] = url

                    # //div[@class="listupd"]/div[@class="mng"]
                    lists = html.xpath('//div[@class="listupd"]/div[@class="mng"]')

                    for list in lists:
                        # div[@class="dtl"]/a[@class="series"]/@href
                        url = list.xpath('div[@class="dtl"]/a[@class="series"]/@href')[0]
                        # 最新の更新情報を取得
                        # div[@class="dtl"]/div[@class="list"]/ul/li[1]/time/@datetime
                        times = list.xpath('div[@class="dtl"]/ul[@class="list"]/li[1]/time/@datetime')

                        if times is not None and len(times) > 0:
                            utc_time = times[0]

                            # UTCの更新時刻をLOCALTIMEに変更
                            dt_utc = datetime.strptime(utc_time, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
                            dt_local = dt_utc.astimezone(ZoneInfo('Asia/Tokyo'))

                            ids[re.sub(r'^https?://[^/]+/', '', url)] = (dt_local.isoformat(), url)

                    return ids
                else:
                    print('Status Error ' + str(response.status_code) + ':' + self.url)
                    return None

            except exceptions.ConnectionError:
                print('ConnectionError:' + self.url)
            except exceptions.Timeout:
                print('Timeout:' + self.url)
            except Exception as e:
                print('Exception:')
                print(e)
                break

            # リトライ前に2秒待つ
            sleep(2)

        return None

    def check(self):
        urls = self.get_urlList()
        files = self.get_fileList()

        if urls is not None:
            for id, url in urls.items():
                if id not in files:
                    print(url) 
        else:
            print('urls is None')

if __name__ == '__main__':
    url = sys.argv[1] if len(sys.argv) > 1 else 'https://raw.senmanga.com/'
    path = sys.argv[2] if len(sys.argv) > 2 else '.'

    print(url, path)
    sen = SenMangaCheck(url, path)
    sen.check()
