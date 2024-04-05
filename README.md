# MTAutoFreeBT
基于馒头APIKEY的RSS刷流工具

# 用法：
```bash
docker run -e QBURL='http://192.168.1.10:8080' -e QBUSER='user' -e QBPWD='password' -e APIKEY='apikey' -e DOWNLOADPATH='/path'  -e CYCLE=1800 -e RSS=url -e SPACE=80  shangling/mt-auto-free-to-qb:latest
```

# 参数说明
```yaml
QBURL  QB的地址
QBUSER QB账户
QBPWD QB密码
DOWNLOADPATH QB的下载路径
APIKEY 馒头的APIKEY
CYCLE 执行获取RSS周期时间（秒）如1800=半小时  3600=一小时
RSS 馒头的RSS订阅地址
SPACE 检测QB剩余空间大小，默认小于80G停止刷流
```
