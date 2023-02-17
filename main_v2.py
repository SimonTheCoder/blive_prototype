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

proxies = {
    'http': "http://127.0.0.1:10811",
    'https': "http://127.0.0.1:10811"
}

config_file_path = './config.json'

if os.path.exists(config_file_path):
    with open(config_file_path) as f:
        config = json.load(f)
else:
    config = {}
    config["roomId"] = ""
    config["key"] = ""
    config["secret"] = ""
    config[""]
    with open(config_file_path, 'w') as f:
        json.dump(config, f)
    print(f"Created new config file at {config_file_path}")
    exit()

print("Loaded config.")


class BiliClient:
    def __init__(self, roomId, key, secret, host = 'live-open.biliapi.com', config=None):
        self.roomId = roomId
        self.key = key
        self.secret = secret
        self.host = host
        self.config = config
        self.session = None
        pass
    
    # 事件循环
    def run(self):
        loop = asyncio.get_event_loop()
        websocket = loop.run_until_complete(self.connect())
        tasks = [
            asyncio.ensure_future(self.recvLoop(websocket)),
            asyncio.ensure_future(self.heartBeat(websocket)), 
            asyncio.ensure_future(self.wsHeartBeat(websocket)), 
        ]
        print("loop start.")
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
        #postUrl = "https://www.google.com/"
        r = requests.post(url=postUrl, headers=headerMap, data=params, verify=False, proxies=proxies)
        print(r)
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

    async def wsHeartBeat(self, websocket):
        while True:
            await asyncio.ensure_future(asyncio.sleep(20))
            print("Sending wsheartBeat ...")
            req = proto.Proto()
            req.op = 2
            await websocket.send(req.pack())
            

    # 项目的心跳包
    async def heartBeat(self, websocket):
        while True:
            await asyncio.ensure_future(asyncio.sleep(20))

            print("Sending heartBeat...")
            postUrl = f"https://{self.host}/v2/app/heartbeat"
            print(postUrl)
            game_id = self.session["data"]["game_info"]["game_id"]
            params = '{"game_id":"%s"}' % (game_id)
            headerMap = self.sign(params)
            r = requests.post(url=postUrl, headers=headerMap, data=params, verify=False)
            result = json.loads(r.content.decode())
            print (result)
            print (r.status_code)     

    # 长链的接受循环
    async def recvLoop(self, websocket):
        print("[BiliClient] run recv...")
        while True:
            try:
                recvBuf = await websocket.recv()
                resp = proto.Proto()
                resp.unpack(recvBuf)

            except websockets.exceptions.ConnectionClosed as e:
                # Handle the "no close frame received or sent" error
                # This may involve logging the error, re-establishing the connection, or terminating the program
                print("WebSocket connection closed: {}".format(str(e))) 
                if e.code != 1000:
                   await websocket.close()  
                print("reconnecting...")
                print(self.session)
                addr = self.session["data"]["websocket_info"]["wss_link"][random.randint(0,2)] #use the last one addr.
                authBody = self.session["data"]["websocket_info"]["auth_body"]
                print(addr, authBody)
                websocket = await websockets.connect(addr)
                await self.auth(websocket, authBody)
                print("reconnecting...OK")

    async def connect(self):
        print("about to connect.")
        if not self.start():
            print("APP start failed. exit.")
            exit(1)

        addr = self.session["data"]["websocket_info"]["wss_link"][-1] #use the last one addr.
        authBody = self.session["data"]["websocket_info"]["auth_body"]
        print(addr, authBody)
        websocket = await websockets.connect(addr)
        await self.auth(websocket, authBody)
        return websocket

    def start(self):

        if os.path.exists("./session.json"):
            print("Make sure the last session is ended.")
            with open("session.json","r") as f:
                old_session = json.load(f)
                self.end(old_session["data"]["game_info"]["game_id"])
            timestamp = str(int(time.time()))
            new_filename = f"./session_{timestamp}.json"
            os.rename("./session.json", new_filename)
            print(f"Renamed session.json to {new_filename}")
        else:
            print("session.json does not exist. save current one.")

        postUrl = f"https://{self.host}/v2/app/start"
        print(postUrl)
        params = '{"code":"%s","app_id":%s}' % (self.config["code"], self.config["app_id"])
        headerMap = self.sign(params)
        r = requests.post(url=postUrl, headers=headerMap, data=params, verify=False)
        self.session = json.loads(r.content.decode())
        print (self.session)
        print (r.status_code) 

        if self.session["code"] == 0:
            print("App start OK! game_id = %s" % self.session["data"]["game_info"]["game_id"])

            with open("session.json","w") as f:
                json.dump(self.session, f)
            return True
        else:
            print("App start failed!!!")

            return False

    def end(self, game_id = None):
        if game_id is None:
            game_id = self.session["data"]["game_info"]["game_id"]
        print("Ending session game_id = %s" % game_id)
        postUrl = f"https://{self.host}/v2/app/end"
        print(postUrl)
        params = '{"app_id":%s,"game_id":"%s"}' % ( self.config["app_id"],game_id)
        headerMap = self.sign(params)
        r = requests.post(url=postUrl, headers=headerMap, data=params, verify=False)
        result = json.loads(r.content.decode())
        print (result)
        print (r.status_code) 

if __name__=='__main__':

    try:
        cli = BiliClient(
            roomId = config["roomId"],
            key = config["key"],
            secret =config["secret"],
            host = "live-open.biliapi.com",
            config = config)
        #cli.start()    
        cli.run()
    except Exception as e:
        print("err", e)
