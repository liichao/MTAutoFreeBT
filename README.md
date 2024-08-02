# MTAutoFreeBT
基于馒头APIKEY的RSS刷流工具

# 直接docker使用用法：
创建.env文件并定义对应环境变量，格式如下：
```
环境变量名1=环境变量值1
环境变量名2=环境变量值2
```
创建docker容器并挂载.env文件和flood_data.json文件到容器内，示例：
```bash
docker run -e QBURL='http://192.168.1.10:8080' shangling/mt-auto-free-to-qb:latest -v ./flood_data.json:/app/flood_data.json -v ./.env:/app/.env
```

# 青龙面板使用用法：
复制[flood.py](./app/flood.py)到青龙面板脚本目录下，在青龙面板的环境变量中添加对应的环境变量，在依赖管理中添加`requests`库，然后在定时任务中添加脚本任务即可，不需要安装`python-dotenv`库也无需创建`.env`文件。

# 参数说明

| 参数名          | 作用描述                              | 默认值                      | 是否可为空 |
|--------------|-----------------------------------|--------------------------|-------|
| QBURL        | QB的地址                             | http://192.168.1.10:8080 | 否     |
| QBUSER       | QB账户                              | admin                    | 否     |
| QBPWD        | QB密码                              | adminadmin               | 否     |
| DOWNLOADPATH | QB的下载路径                           | /download/PT刷流           | 否     |
| APIKEY       | 馒头的APIKEY                         | apikey                   | 否     |
| CYCLE        | 执行获取RSS周期时间，单位为小时（支持小数，青龙面板不需要此变量） | 0.5                     | 是     |
| RSS          | 馒头的RSS订阅地址，需要勾选`[大小]`选项，否则无法获取种子大小                        | url                      | 否     |
| SPACE        | 检测QB剩余空间大小，默认小于80G停止刷流            | 80                       | 是     |
| BOT_TOKEN    | TG的token不配置默认不推送                  | None                | 是     |
| CHAT_ID      | TG的chatid                         | 646111111                | 是     |
| GET_METHOD   | 配置推送QB的方法   True/False            | False                    | 是     |
| MAX_SIZE     | 配置最大种子大小，单位为GB，超过此大小不推送 | 30                       | 是     |
| MIN_SIZE     | 配置最小种子大小，单位为GB，小于此大小不推送 | 1                        | 是     |
| FREE_TIME    | 配置种子最少剩余免费时间，单位为小时，小于此时间不推送 | 10                       | 是     |
| PUBLISH_BEFORE | 配置种子已发布时长，单位为小时，大于此时长不推送 | 24                       | 是     |
| PROXY        | 配置访问MT的代理地址，如`http://127.0.0.1:7890`，不需要代理请勿添加此变量 | None                     | 是     |
| TAGS         | 配置刷流的种子的TAG，多个TAG用`,`分隔，如`tag1,tag2` | MT刷流                   | 是     |
| LS_RATIO     | 配置刷流的种子的最低`下载数/做种数`比例，小于此值不推送 | 1.0                      | 是     |



```
GET_METHOD:
    True/False
    True为程序下载下来种子然后推送给QB，
    False为程序推送下载链接给QB由QB服务器自行下载种子
    目的为避免QB服务器无法访问馒头，导致添加种子失败。
```