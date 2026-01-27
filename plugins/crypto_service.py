# plugins/crypto_service.py
from interface import Neuron
import hashlib
import base64
# import time

class Plugin(Neuron):
    def start(self):
        self.api.log("加密服务中心已启动，监听 req:sign ...")
        self.api.on("req:sign", self.handle_sign_request)

    def stop(self):
        self.api.log("加密服务下线")

    def handle_sign_request(self, payload, request_id):
        self.api.log(f"处理请求 ID: {request_id}")
        
        # 模拟计算
        digest = hashlib.sha256(payload.encode()).hexdigest()
        signature = base64.b64encode(digest.encode()).decode()
        
        response = {
            "payload": payload,
            "signature": signature,
            "processor": "CryptoService_v1"
        }
        
        # 定向回复
        reply_event = f"res:sign:{request_id}"
        self.api.impulse(reply_event, result=response)