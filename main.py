import asyncio
import json
import websockets
import requests
import time
import hashlib
import hmac
import random
from hashlib import sha256
import proto

import os
import json

config_file_path = './config.json'

if os.path.exists(config_file_path):
    with open(config_file_path) as f:
        config = json.load(f)
else:
    config = {}
    config["roomId"] = ""
    config["key"] = ""
    config["secret"] = ""
    with open(config_file_path, 'w') as f:
        json.dump(config, f)
    print(f"Created new config file at {config_file_path}")
    exit()

print("Loaded config.")


class BiliClient:
    def __init__(self, roomId, key, secret, host = 'live-open.biliapi.com'):
        self.roomId = roomId
        self.key = key
        self.secret = secret
        self.host = host
        pass
    
    # 事件循环
    def run(self):
        loop = asyncio.get_event_loop()
        websocket = loop.run_until_complete(self.connect())
        tasks = [
            asyncio.ensure_future(self.recvLoop(websocket)),
            asyncio.ensure_future(self.heartBeat(websocket)), 
        ]
        loop.run_until_complete(asyncio.gather(*tasks))

    # http的签名
    def sign(self, params):
        key = self.key
        secret = self.secret
        md5 = hashlib.md5()
        md5.update(params.encode())
        ts = time.time()
        nonce = random.randint(1,100000)+time.time()
        md5data = md5.hexdigest()
        headerMap = {
        "x-bili-timestamp": str(int(ts)),
        "x-bili-signature-method": "HMAC-SHA256",
        "x-bili-signature-nonce": str(nonce),
        "x-bili-accesskeyid": key,
        "x-bili-signature-version": "1.0",
        "x-bili-content-md5": md5data,
        }

        headerList = sorted(headerMap)
        headerStr = ''

        for key in headerList:
            headerStr = headerStr+ key+":"+str(headerMap[key])+"\n"
        headerStr = headerStr.rstrip("\n")

        appsecret = secret.encode() 
        data = headerStr.encode()
        signature = hmac.new(appsecret, data, digestmod=sha256).hexdigest()
        headerMap["Authorization"] = signature
        headerMap["Content-Type"] = "application/json"
        headerMap["Accept"] = "application/json"
        return headerMap

    # 获取长链信息
    def websocketInfoReq(self, postUrl, params):
        headerMap = self.sign(params)
        r = requests.post(url=postUrl, headers=headerMap, data=params, verify=False)
        data = json.loads(r.content)
        print(data)
        return "ws://" + data['data']['host'][0]+":"+str(data['data']['ws_port'][0])+"/sub", data['data']['auth_body']

    # 长链的auth包
    async def auth(self, websocket, authBody):
        req = proto.Proto()
        req.body = authBody
        req.op = 7
        await websocket.send(req.pack())
        buf = await websocket.recv()
        resp = proto.Proto()
        resp.unpack(buf)
        respBody = json.loads(resp.body)
        if respBody["code"] != 0:
            print("auth 失败")
        else:
            print("auth 成功")

    # 长链的心跳包
    async def heartBeat(self, websocket):
        while True:
            await asyncio.ensure_future(asyncio.sleep(20))
            req = proto.Proto()
            req.op = 2
            await websocket.send(req.pack())
            print("[BiliClient] send heartBeat success")

    # 长链的接受循环
    async def recvLoop(self, websocket):
        print("[BiliClient] run recv...")
        while True:
            recvBuf = await websocket.recv()
            resp = proto.Proto()
            resp.unpack(recvBuf)

    async def connect(self):
        postUrl = "https://%s/v1/common/websocketInfo"%self.host
        params = '{"room_id":%s}'%self.roomId
        addr, authBody = self.websocketInfoReq(postUrl, params)
        print(addr, authBody)
        websocket = await websockets.connect(addr)
        await self.auth(websocket, authBody)
        return websocket

if __name__=='__main__':
    try:
        cli = BiliClient(
            roomId = 23105976,
            key = "",
            secret = "",
            host = "live-open.biliapi.com")
        cli.run()
    except Exception as e:
        print("err", e)
