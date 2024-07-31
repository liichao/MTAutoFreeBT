import requests
import time
import xml.etree.ElementTree as ET
import os
import re
import random
import logging
import argparse
from datetime import datetime, timedelta

# 配置日志记录器
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# 创建ArgumentParser对象
parser = argparse.ArgumentParser()

# 添加命令行参数
parser.add_argument(
    "--qburl",
    default=os.environ.get("QBURL", "http://192.168.66.10:10000"),
    help="QB 的网址",
)
parser.add_argument(
    "--qbuser", default=os.environ.get("QBUSER", "admin"), help="QB账户"
)
parser.add_argument(
    "--qbpwd", default=os.environ.get("QBPWD", "adminadmin"), help="QB密码"
)
parser.add_argument(
    "--apikey",
    default=os.environ.get("APIKEY", "70390435-35fb-44e8-a207-fcd6be7099ef"),
    help="馒头的api key",
)
parser.add_argument(
    "--downloadpath",
    default=os.environ.get("DOWNLOADPATH", "/download/PT刷流"),
    help="指定默认下载目录",
)
parser.add_argument(
    "--cycle", default=os.environ.get("CYCLE", "1800"), help="循环周期 秒"
)
parser.add_argument("--rss", default=os.environ.get("RSS", "url"), help="馒头RSS地址")
parser.add_argument(
    "--space", default=os.environ.get("SPACE", 80), help="空间小于多少后不再刷流(G)"
)
parser.add_argument(
    "--max_size",
    default=os.environ.get("MAX_SIZE", 30),
    help="最大种子大小(G)",
)
parser.add_argument(
    "--min_size",
    default=os.environ.get("MIN_SIZE", 1),
    help="最小种子大小(G)",
)
parser.add_argument(
    "--bot_token", default=os.environ.get("BOT_TOKEN", None), help="TG机器人"
)
parser.add_argument(
    "--chat_id", default=os.environ.get("CHAT_ID", "646111111"), help="TG机器人"
)
parser.add_argument(
    "--get_method",
    default=os.environ.get("GET_METHOD", False),
    help="推送种子的方法",
)
parser.add_argument(
    "--free_time",
    default=os.environ.get("FREE_TIME", 10),
    help="剩余免费时间 小时",
)
# 解析命令行参数
args = parser.parse_args()

QB_URL = args.qburl
QBUSER = args.qbuser
QBPWD = args.qbpwd
MT_APIKEY = args.apikey
DOWNLOADPATH = args.downloadpath
CYCLE = int(args.cycle)
RSS = args.rss
SPACE = int(float(args.space) * 1024 * 1024 * 1024)
BOT_TOKEN = args.bot_token
CHAT_ID = int(args.chat_id)
GET_METHOD = args.get_method
MAX_SIZE = int(float(args.max_size) * 1024 * 1024 * 1024)
MIN_SIZE = int(float(args.min_size) * 1024 * 1024 * 1024)
FREE_TIME = int(float(args.free_time) * 60 * 60)

NAMESPACE = {"dc": "http://purl.org/dc/elements/1.1/"}

last_rss_time = None

qb_session = requests.Session()
mt_session = requests.Session()


# 添加Telegram通知
def send_telegram_message(message):
    if BOT_TOKEN is None:
        return
    logging.info(f"发送消息通知到TG{message}")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    params = {"chat_id": CHAT_ID, "text": message}
    try:
        response = requests.get(url, params=params)
    except requests.exceptions.RequestException as e:
        logging.error(f"发送TG通知失败，请求异常：{e}")
        return
    if response.status_code == 200:
        logging.info("消息发送成功！")
    else:
        logging.info("消息发送失败！")


# 从MT获取种子信息
def get_torrent_detail(torrent_id):
    url = "https://api.m-team.cc/api/torrent/detail"
    try:
        response = mt_session.post(url, data={"id": torrent_id})
    except requests.exceptions.RequestException as e:
        logging.error(f"种子信息获取失败，请求异常：{e}")
        return None
    try:
        data = response.json()["data"]
        name = data["name"]
        size = int(data["size"])
        discount = data["status"].get("discount", None)
        discount_end_time = data["status"].get("discountEndTime", None)
        if discount_end_time is not None:
            discount_end_time = datetime.strptime(
                discount_end_time, "%Y-%m-%d %H:%M:%S"
            )
    except (ValueError, KeyError) as e:
        logging.warning(f"response信息为{response.text}")
        logging.error(f"种子信息解析失败：{e}")
        return None
    return name, size, discount, discount_end_time


# 添加种子下载地址到QBittorrent
def add_torrent(url, name):
    add_torrent_url = QB_URL + "/api/v2/torrents/add"
    torrent_data = {"urls": url, "savepath": DOWNLOADPATH}
    if GET_METHOD:
        logging.info(f"使用保存种子方式给QB服务器添加种子")
        try:
            response = requests.get(url)
        except requests.exceptions.RequestException as e:
            logging.error(f"种子下载异常：{e}")
            return
        if response.status_code != 200:
            logging.error(f"种子文件下载失败，HTTP状态码: {response.status_code}")
            return
        try:
            response = qb_session.post(
                add_torrent_url, files={"file": response.content}
            )
        except requests.exceptions.RequestException as e:
            logging.error(f"种子添加异常：{e}")
            return
    else:
        logging.info(f"使用推送URL给QB服务器方式添加种子")
        try:
            response = qb_session.post(add_torrent_url, data=torrent_data)
        except requests.exceptions.RequestException as e:
            logging.error(f"种子添加异常：{e}")
            return

    if response.status_code == 200:
        status = f"{name}种子添加成功！"
    else:
        status = f"{name}种子添加失败！"
    logging.info(status)
    send_telegram_message(status)


# 当磁盘小于80G时停止刷流
def get_disk_space():
    url = QB_URL + "/api/v2/sync/maindata"
    try:
        response = qb_session.get(url)
    except requests.exceptions.RequestException as e:
        logging.error(f"获取磁盘空间失败，请求异常：{e}")
        return None
    if response.status_code != 200:
        logging.error(f"获取磁盘空间失败，HTTP状态码: {response.status_code}")
        return None
    data = response.json()
    try:
        disk_space = int(data["server_state"]["free_space_on_disk"])
    except (KeyError, ValueError) as e:
        logging.error(f"获取磁盘空间失败，解析异常：{e}")
        return None
    logging.info(f"当前磁盘空间为:{disk_space / 1024 / 1024 / 1024:.2f}G")
    return disk_space


# 从MT获取种子下载地址
def get_torrent_url(torrent_id):
    url = "https://api.m-team.cc/api/torrent/genDlToken"
    try:
        response = mt_session.post(url, data={"id": torrent_id})
    except requests.exceptions.RequestException as e:
        logging.error(f"获取种子地址失败，请求异常：{e}")
        return None
    if response.status_code != 200:
        logging.error(f"获取种子地址失败，HTTP状态码: {response.status_code}")
        return None
    try:
        data = response.json()["data"]
        download_url = (
            f'{data.split("?")[0]}?useHttps=true&type=ipv6&{data.split("?")[1]}'
        )
    except (KeyError, ValueError) as e:
        logging.warning(f"response信息为{response.text}")
        logging.error(f"种子地址解析失败：{e}")
        return None
    return download_url


# 每隔一段时间访问MT获取RSS并添加种子到QBittorrent
def flood_task():
    global last_rss_time
    logging.info("开始获取馒头RSS数据")
    disk_space = get_disk_space()
    if disk_space is None:
        return
    elif disk_space <= SPACE:
        logging.info("磁盘空间不足，停止刷流")
        return
    try:
        response = mt_session.get(RSS)
    except requests.exceptions.RequestException as e:
        logging.error(f"RSS请求失败：{e}")
        return
    if response.status_code != 200:
        logging.error(f"获取RSS失败，HTTP状态码: {response.status_code}")
        return
    logging.info("RSS数据获取成功")
    try:
        root = ET.fromstring(response.text)
    except ET.ParseError as e:
        logging.error(f"XML解析失败：{e}")
        return

    current_rss_time = datetime.now()
    for item in root.findall("channel/item", NAMESPACE):
        link = item.find("link").text
        torrent_id = re.search(r"\d+$", link).group()
        publish_time = item.find("pubDate").text
        publish_time = datetime.strptime(publish_time, "%a, %d %b %Y %H:%M:%S %Z")
        # 如果发布时间在上次运行时间之前，则跳过
        if last_rss_time is not None and publish_time <= last_rss_time:
            logging.info(f"种子{torrent_id}并非新种，跳过")
            continue
        logging.info(f"开始获取种子{torrent_id}信息")
        time.sleep(random.randint(5, 10))
        detail = get_torrent_detail(torrent_id)
        if detail is None:
            continue
        name, size, discount, discount_end_time = detail
        if size is None or discount is None:
            logging.info(
                f"种子{torrent_id}非免费或请求异常，忽略种子，大小为{size},状态为：{discount}"
            )
            continue
        if discount not in ["FREE", "_2X_FREE"]:
            logging.info(f"种子{torrent_id}非免费资源，忽略种子，状态为：{discount}")
            continue
        if (
            discount_end_time is not None
            and discount_end_time < datetime.now() + timedelta(seconds=FREE_TIME)
        ):
            logging.info(
                f"种子{torrent_id}剩余免费时间小于{FREE_TIME/60/60:.2f}小时，忽略种子"
            )
            continue
        if size > MAX_SIZE:
            logging.info(
                f"种子{torrent_id}大小超过{MAX_SIZE/1024/1024/1024:.2f}G，忽略种子"
            )
            continue
        if size < MIN_SIZE:
            logging.info(
                f"种子{torrent_id}大小小于{MIN_SIZE/1024/1024/1024:.2f}G，忽略种子"
            )
            continue
        if disk_space - size < SPACE:
            logging.info(
                f"种子{torrent_id}大小为{size}，下载后磁盘空间将小于{SPACE/1024/1024/1024:.2f}G，忽略种子"
            )
            continue
        logging.info(
            f"{name}种子{torrent_id}，大小为{size/1024/1024/1024:.2f}G,状态为：{discount}"
        )
        time.sleep(random.randint(5, 10))
        download_url = get_torrent_url(torrent_id)
        if download_url is None:
            continue
        add_torrent(download_url, name)

    last_rss_time = current_rss_time


def taskloop():
    while True:
        flood_task()
        logging.info(f"完成本次循环，等待下一次循环。")
        time.sleep(CYCLE)  # 等待半个小时


if __name__ == "__main__":
    # 检查本地是否存在qb_cookie.pickle文件，如果存在则直接读取cookie
    login_url = QB_URL + "/api/v2/auth/login"
    login_data = {"username": QBUSER, "password": QBPWD}
    qb_session.post(login_url, data=login_data)
    mt_session.headers.update({"x-api-key": MT_APIKEY})
    taskloop()
