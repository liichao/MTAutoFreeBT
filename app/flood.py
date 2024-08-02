import requests
import time
import xml.etree.ElementTree as ET
import os
import re
import random
import logging
from datetime import datetime, timedelta
import json

# 配置日志记录器
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

QBURL = os.environ.get("QBURL", "http://192.168.66.10:10000")
QBUSER = os.environ.get("QBUSER", "admin")
QBPWD = os.environ.get("QBPWD", "adminadmin")
APIKEY = os.environ.get("APIKEY", "70390435-35fb-44e8-a207-fcd6be7099ef")
DOWNLOADPATH = os.environ.get("DOWNLOADPATH", "/download/PT刷流")

RSS = os.environ.get("RSS", "url")
SPACE = int(float(os.environ.get("SPACE", 80)) * 1024 * 1024 * 1024)
BOT_TOKEN = os.environ.get("BOT_TOKEN", None)
CHAT_ID = int(os.environ.get("CHAT_ID", "646111111"))
GET_METHOD = os.environ.get("GET_METHOD", False)
MAX_SIZE = int(float(os.environ.get("MAX_SIZE", 30)) * 1024 * 1024 * 1024)
MIN_SIZE = int(float(os.environ.get("MIN_SIZE", 1)) * 1024 * 1024 * 1024)
FREE_TIME = int(float(os.environ.get("FREE_TIME", 10)) * 60 * 60)
PUBLISH_BEFORE = int(float(os.environ.get("PUBLISH_BEFORE", 24)) * 60 * 60)
PROXY = os.environ.get("PROXY", None)
TAGS = os.environ.get("TAGS", "MT刷流")
LS_RATIO = float(os.environ.get("LS_RATIO", 1))

DATA_FILE = "flood_data.json"

qb_session = requests.Session()
mt_session = requests.Session()
flood_torrents = []


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
        seeders = int(data["status"]["seeders"])
        leechers = int(data["status"]["leechers"])
        if discount_end_time is not None:
            discount_end_time = datetime.strptime(
                discount_end_time, "%Y-%m-%d %H:%M:%S"
            )
    except (ValueError, KeyError) as e:
        logging.warning(f"response信息为{response.text}")
        logging.error(f"种子信息解析失败：{e}")
        return None
    return {
        "name": name,
        "size": size,
        "discount": discount,
        "discount_end_time": discount_end_time,
        "seeders": seeders,
        "leechers": leechers,
    }


# 添加种子下载地址到QBittorrent
def add_torrent(url, name):
    global flood_torrents
    add_torrent_url = QBURL + "/api/v2/torrents/add"
    if GET_METHOD:
        logging.info(f"使用保存种子方式给QB服务器添加种子")
        try:
            response = mt_session.get(url)
        except requests.exceptions.RequestException as e:
            logging.error(f"种子下载异常：{e}")
            return False
        if response.status_code != 200:
            logging.error(f"种子文件下载失败，HTTP状态码: {response.status_code}")
            return False
        try:
            response = qb_session.post(
                add_torrent_url,
                data={
                    "torrents": response.content,
                    "tags": TAGS,
                    "savepath": DOWNLOADPATH,
                },
            )
        except requests.exceptions.RequestException as e:
            logging.error(f"种子添加异常：{e}")
            return False
    else:
        logging.info(f"使用推送URL给QB服务器方式添加种子")
        try:
            response = qb_session.post(
                add_torrent_url,
                data={"urls": url, "savepath": DOWNLOADPATH, "tags": TAGS},
            )
        except requests.exceptions.RequestException as e:
            logging.error(f"种子添加异常：{e}")
            return False

    if response.status_code != 200:
        logging.error(f"种子{name}添加失败！HTTP状态码：{response.status_code}")
        return False

    logging.info(f"种子{name}添加成功！")
    send_telegram_message(f"种子{name}添加成功！")
    return True


# 当磁盘小于80G时停止刷流
def get_disk_space():
    url = QBURL + "/api/v2/sync/maindata"
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
    global flood_torrents
    logging.info("开始刷流")
    disk_space = get_disk_space()
    if disk_space is None:
        return
    elif disk_space <= SPACE:
        logging.info("磁盘空间不足，停止刷流")
        send_telegram_message(
            f"磁盘空间不足，停止刷流，当前剩余空间为{disk_space/1024/1024/1024:.2f}G"
        )
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

    NAMESPACE = {"dc": "http://purl.org/dc/elements/1.1/"}
    for item in root.findall("channel/item", NAMESPACE):
        link = item.find("link").text
        torrent_id = re.search(r"\d+$", link).group()
        publish_time = item.find("pubDate").text
        publish_time = datetime.strptime(publish_time, "%a, %d %b %Y %H:%M:%S %Z")
        title = item.find("title").text
        matches = re.findall(
            r"\[(\d+(\.\d+)?)\s(B|KB|MB|GB|TB|PB)\]", title.replace(",", "")
        )
        if not matches:
            logging.info(
                f"种子{torrent_id}大小解析失败，可能是生成的RSS链接未勾选[大小]，标题为：{title}"
            )
            continue
        # 取最后一个匹配的组
        size, unit = matches[-1][0], matches[-1][2]
        UNIT_LIST = ["B", "KB", "MB", "GB", "TB", "PB"]
        size = int(float(size) * 1024 ** UNIT_LIST.index(unit))

        # 如果已经添加过该种子则跳过
        if any(torrent_id == torrent["id"] for torrent in flood_torrents):
            logging.info(f"种子{torrent_id}已经添加过，跳过")
            continue
        # 如果发布时间超过PUBLISH_BEFORE则跳过
        if datetime.now() - publish_time > timedelta(seconds=PUBLISH_BEFORE):
            logging.info(
                f"种子{torrent_id}发布时间超过{PUBLISH_BEFORE/60/60:.2f}小时，跳过"
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
        logging.info(f"开始获取种子{torrent_id}信息")
        time.sleep(random.randint(5, 10))
        detail = get_torrent_detail(torrent_id)
        if detail is None:
            continue

        name = detail["name"]
        discount = detail["discount"]
        discount_end_time = detail["discount_end_time"]
        seeders = detail["seeders"]
        leechers = detail["leechers"]

        if discount is None:
            logging.info(
                f"种子{torrent_id}非免费或请求异常，忽略种子, 信息为：{detail}"
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
        if seeders <= 0:
            logging.info(f"种子{torrent_id}无人做种，忽略种子")
            continue
        if leechers / seeders <= LS_RATIO:
            logging.info(f"种子{torrent_id}下载/做种比例小于{LS_RATIO}，忽略种子")
            continue

        logging.info(
            f"{name}种子{torrent_id}，大小为{size/1024/1024/1024:.2f}G,状态为：{discount}"
        )
        time.sleep(random.randint(5, 10))
        download_url = get_torrent_url(torrent_id)
        if download_url is None:
            continue
        if not add_torrent(download_url, name):
            continue
        disk_space -= size
        flood_torrents.append(
            {
                "name": name,
                "id": torrent_id,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "size": size,
                "url": download_url,
                "discount": discount,
                "discount_end_time": (
                    discount_end_time.strftime("%Y-%m-%d %H:%M:%S")
                    if discount_end_time is not None
                    else None
                ),
            }
        )
        if disk_space <= SPACE:
            logging.info("磁盘空间不足，停止刷流")
            send_telegram_message(
                f"磁盘空间不足，停止刷流，当前剩余空间为{disk_space/1024/1024/1024:.2f}G"
            )
            break


def login():
    login_url = QBURL + "/api/v2/auth/login"
    login_data = {"username": QBUSER, "password": QBPWD}
    try:
        response = qb_session.post(login_url, data=login_data)
    except requests.exceptions.RequestException as e:
        logging.error(f"QBittorrent登录失败，请求异常：{e}")
        return False
    if response.status_code != 200:
        logging.error(f"QBittorrent登录失败，HTTP状态码: {response.status_code}")
        return False
    mt_session.headers.update({"x-api-key": APIKEY})
    if PROXY:
        mt_session.proxies = {"http": PROXY, "https": PROXY}
    return True


def read_config():
    global flood_torrents
    if not os.path.exists(DATA_FILE):
        return
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        flood_torrents = json.load(f)
    if not isinstance(flood_torrents, list):
        flood_torrents = []


def save_config():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(flood_torrents, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    read_config()
    if not login():
        logging.error("QB登录失败，程序退出。")
        exit(1)
    flood_task()
    save_config()
