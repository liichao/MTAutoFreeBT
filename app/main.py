import requests
import time
import pickle
import xml.etree.ElementTree as ET
import os
import re
import random
import logging
import argparse

# 配置日志记录器
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 提取MT URL中的数字ID部分
def extract_numeric_part(url):
    numeric_part = re.search(r'\d+', url).group()
    return numeric_part

# 提取JSON响应中的size、discount和discountEndTime值
def extract_values_from_json(response_json):
    try:
        size = response_json['data']['size']
        discount = response_json['data']['status']['discount']
        discount_end_time = response_json['data']['status']['discountEndTime']
        return size, discount, discount_end_time
    except (KeyError, TypeError) as e:
        logging.error(f'提取值错误：{e}')
        return None, None, None


# POST请求获取JSON响应
def get_json_response(payload):
    url = 'https://kp.m-team.cc/api/torrent/detail'
    headers = {'x-api-key': MT_APIKEY}
    try:
        # response = requests.post(url, json=payload, headers=headers)
        response = requests.request("POST", url, headers=headers, data=payload)
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f'请求失败：{e}')
        return None
    except ValueError as e:
        logging.warning(f'response信息为{response.text()}')
        logging.error(f'JSON解析失败：{e}')
        return None
# 持久化保存QBittorrent的cookie
def save_cookie(cookie):
    with open('../../mq-qb/qb_cookie.pickle', 'wb') as f:
        pickle.dump(cookie, f)


# 添加种子下载地址到QBittorrent
def add_torrent(url):
    add_torrent_url = QB_URL + '/api/v2/torrents/add'
    torrent_data = {'urls': url, 'savepath': DOWNLOADPATH}
    with open('../../mq-qb/qb_cookie.pickle', 'rb') as f:
        cookie = pickle.load(f)
    response = requests.request("POST", add_torrent_url, data=torrent_data, cookies={'SID': cookie})
    if response.status_code == 200:
        logging.info('种子添加成功！')
    else:
        logging.info('种子添加失败！')

# 当磁盘小于80G时停止刷流
def get_disk_space():
    url = f"{QB_URL}/api/v2/sync/maindata"
    with open('../../mq-qb/qb_cookie.pickle', 'rb') as f:
        cookie = pickle.load(f)
    response = requests.request('GET', url, cookies={'SID': cookie})
    if response.status_code == 200:
        data = response.json()
        disk_space = data['server_state']['free_space_on_disk']
        try:
            disk_space_gb = int(disk_space) / 1024 / 1024 / 1024
        except ValueError:
            print("磁盘空间转换为GB时出错，使用默认值")
            disk_space_gb = 0  # 使用默认值
        logging.info(f'当前磁盘空间为:{disk_space_gb}。')
        if int(disk_space_gb) < SPACE:
            return True
    else:
        return False

# 处理discount值为FREE的情况
def handle_free_discount(payload):
    url = 'https://kp.m-team.cc/api/torrent/genDlToken'
    headers = {'x-api-key': MT_APIKEY}
    try:
        time.sleep(random.randint(5, 10))
        response = requests.request("POST", url, headers=headers, data=payload)
        if response.status_code == 200:
            response_json = response.json()
            if response_json['message'] == 'SUCCESS':
                download_url_info = response_json['data']
                download_url = f'{download_url_info.split("?")[0]}?useHttps=true&type=ipv6&{download_url_info.split("?")[1]}'
                logging.info(f'开始添加种子：{download_url}')
                # 推送给QBittorrent
                add_torrent(download_url)
    except requests.exceptions.RequestException as e:
        logging.error(f'请求失败：{e}，忽略添加下载')

# 每隔一段时间访问MT获取RSS并添加种子到QBittorrent
def access_mt_and_add_torrent():
    # 定义命名空间映射
    ns = {'dc': 'http://purl.org/dc/elements/1.1/'}
    logging.info('开始获取馒头rss数据')
    while True:
        if get_disk_space():
            pass
        else:
            try:
                response = requests.get(RSS, headers={'x-api-key': MT_APIKEY})
                if response.status_code == 200:
                    logging.info("获取RSS正常")
                    root = ET.fromstring(response.text)
                    for item in root.findall('channel/item', ns):
                        link = item.find('link').text
                        numeric_part = extract_numeric_part(link)
                        logging.info(f"开始确认{numeric_part}是否是免费资源")
                        payload = {'id': numeric_part}
                        time.sleep(random.randint(5, 10))
                        response_json = get_json_response(payload)
                        size, discount, discount_end_time = extract_values_from_json(response_json)
                        # 不需要判断discount_end_time，因为只有FREE或是2X FREE时才需要这个值
                        if size is None or discount is None:
                            logging.info(f"种子{numeric_part}非免费或请求异常，忽略种子，大小为{size},状态为：{discount}")
                            continue
                        else:
                            # to-do 异常json处理
                            logging.info(f"种子{numeric_part}，大小为{'{:.2f}'.format(int(size)/1024/1024/1024)}G,状态为：{discount}")
                            #logging.info(f"size: {size}, discount: {discount}, discount_end_time: {discount_end_time}")
                            if int(size) < 34270510600:
                                if discount in ['FREE', '_2X_FREE']:
                                    # 开始获取下载地址
                                    handle_free_discount(payload)
                else:
                    logging.error('获取RSS失败！')
            except requests.exceptions.RequestException as e:
                logging.error(f'请求失败：{e}')
            except ET.ParseError as e:
                logging.error(f'XML解析失败：{e}')
        time.sleep(CYCLE)  # 等待半个小时


if __name__ == '__main__':
    # 创建ArgumentParser对象
    parser = argparse.ArgumentParser(description="Description of your program")

    # 添加命令行参数
    parser.add_argument('--qburl', default=os.environ.get('QBURL', 'http://192.168.66.10:10000'), help='QB 的网址')
    parser.add_argument('--qbuser', default=os.environ.get('QBUSER', 'admin'), help='QB账户')
    parser.add_argument('--qbpwd', default=os.environ.get('QBPWD', 'adminadmin'), help='QB密码')
    parser.add_argument('--apikey', default=os.environ.get('APIKEY', '70390435-35fb-44e8-a207-fcd6be7099ef'), help='馒头的api key')
    parser.add_argument('--downloadpath', default=os.environ.get('DOWNLOADPATH', '/download/PT刷流'), help='指定默认下载目录')
    parser.add_argument('--cycle', default=os.environ.get('CYCLE', '1800'), help='循环周期 秒')
    parser.add_argument('--rss', default=os.environ.get('RSS', 'url'), help='馒头RSS地址')
    parser.add_argument('--space', default=os.environ.get('SPACE', 80), help='馒头RSS地址')
     # 解析命令行参数
    args = parser.parse_args()

    # 获取参数值
    global MT_APIKEY,QB_URL, DOWNLOADPATH, CYCLE,RSS,SPACE
    QB_URL = args.qburl
    QBUSER = args.qbuser
    QBPWD = args.qbpwd
    MT_APIKEY = args.apikey
    DOWNLOADPATH = args.downloadpath
    CYCLE = int(args.cycle)
    RSS = args.rss
    SPACE = int(args.space)

    # 检查本地是否存在qb_cookie.pickle文件，如果存在则直接读取cookie
    if os.path.exists('qb_cookie.pickle'):
        with open('../../mq-qb/qb_cookie.pickle', 'rb') as f:
            cookie = pickle.load(f)
    else:
        # 登录QBittorrent获取cookie
        login_url = QB_URL + '/api/v2/auth/login'
        login_data = {'username': QBUSER, 'password': QBPWD}
        response = requests.post(login_url, data=login_data)
        cookie = response.cookies.get('SID')
        # 保存cookie
        save_cookie(cookie)
    access_mt_and_add_torrent()
