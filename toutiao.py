import requests
import json
from requests.exceptions import ConnectionError,RequestException
from urllib.parse import urlencode
from bs4 import BeautifulSoup
import re
from json.decoder import JSONDecodeError
from spider.config import *
import pymongo
import os
from hashlib import md5
from multiprocessing import Pool

client = pymongo.MongoClient(MONGO_URL)
db = client[MONGO_DB]

#1.获取索引页的url
def get_page_index(offset,keyword):
    data = {
        'aid':24,
        'app_name':'web_search',
        'offset':offset,
        'format':' json',
        'keyword':keyword,
        'autoload':'true',
        'count':20,
        'en_qc':1,
        'cur_tab':1,
        'from':'search_tab',
        'pd':'synthesis'
    }
    url = 'https://www.toutiao.com/api/search/content/?' +urlencode(data)
    print('index'+':'+url)
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.content.decode()
        return None
    except RequestException:
        print("请求索引页出错")
        return None
#2.解析index数据
def parse_index_page(html):
    try:
        data = json.loads(html)
        if data and 'data' in data.keys():
            for item in data.get('data'):
                if item.get('article_url') is not None and '*' not in item.get('article_url'):
                    #https://www.toutiao.com/a6667379845762122247/
                    #http://toutiao.com/group/6667379845762122247/
                    yield item.get('article_url').replace('group/','a')
                    #yield item.get('article_url')
    except JSONDecodeError:
        pass


#3.获取详情页
def get_page_detail(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.content.decode()
        return None
    except RequestException:
        print("请求详情页出错",url)
        return None
#4.解析详情页
def parse_page_detail(html,url):
#    soup = BeautifulSoup(html,'lxml')
#    title = soup.select('title')[0].get_text()
    title = re.search(r"BASE_DATA.galleryInfo.*?title: '(.*?)',", html, re.S)
    if title is not None:
        title = title.group(1)
   # print(title)
    results = re.search(r'BASE_DATA.galleryInfo.*?gallery: JSON.parse\((.*?)\)', html, re.S)
    if results:
        #print(type(results.group(1)))
        #print(results.group(1).replace('\\', ''))
        data = json.loads(results.group(1))
        data = json.loads(data)
        #print(type(data))
        # print(data)
        #data = re.findall(r'"url_list":[{(.*?)}]', data, re.S)
        #print(data)
        if data and 'sub_images' in data.keys():
            sub_images = data.get('sub_images')
            images = [item.get('url') for item in sub_images]
            for image in images:
                download_image(image)
            return{
                'title':title,
                'url':url,
                'images':images
            }
#5.存储到MongoDB
def save_to_mongo(results):
    if results is not None:
        if db[MONGO_TABLE].insert(results):
            print('存储到MongoDB成功',results)
            return True
    return False
#6.下载图片
def download_image(url):
    print("正在下载：", url)
    try:
        response = requests.get(url)
        if response.status_code == 200:
            save_image(response.content)
        return None
    except RequestException:
        print("下载图片出错",url)
        return None
#7.保存图片
def save_image(content):
    #文件名用md5加密，防止下载重复
    file_path = '{0}/{1}.{2}'.format(os.getcwd(), md5(content).hexdigest(), 'jpg')
    if not os.path.exists(file_path):
        with open(file_path, 'wb') as f:
            f.write(content)
            f.close()
def main(offset):
    html = get_page_index(offset, KEYWORD)
    #print(html)
    for url in parse_index_page(html):
        #print(url)
        html = get_page_detail(url)
        #print(html)
        if html:
            results = parse_page_detail(html, url)
            #print(results)
            save_to_mongo(results)

if __name__ == '__main__':
    pool = Pool()
    groups = ([x*20 for x in range(GROUP_START, GROUP_END+1)])#改变offset
    pool.map(main, groups)
    pool.close()
    pool.join()
