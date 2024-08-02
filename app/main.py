import os
import time
import dotenv
import logging

dotenv.load_dotenv(verbose=True, override=True)
from flood import flood_task, login, read_config, save_config

CYCLE = int(os.environ.get("CYCLE", "1800"))

if __name__ == "__main__":
    read_config()
    if not login():
        logging.error("QB登录失败，程序退出。")
        exit(1)
    while True:
        flood_task()
        save_config()
        logging.info(f"完成本次循环，等待下一次循环。")
        time.sleep(CYCLE)
