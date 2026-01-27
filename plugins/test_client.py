# plugins/crypto_service.py

from interface import IPlugin
import hashlib
import base64

class Plugin(IPlugin):
    def start(self):
        self.api.log("加密服务中心已启动，等待签名请求...")
        # 监听所有签名请求
        self.api.on("req:sign", self.handle_sign_request)

    def stop(self):
        self.api.log("加密服务中心下线")

    def handle_sign_request(self, payload, request_id):
        """处理签名请求并点对点回复"""
        self.api.log(f"正在处理来自 {request_id} 的请求...")
        
        # 模拟业务耗时
        # time.sleep(0.1) 
        
        # 简单的模拟签名逻辑 (Base64 + Hash)
        digest = hashlib.sha256(payload.encode()).hexdigest()
        signature = base64.b64encode(digest.encode()).decode()
        
        response_data = {
            "payload": payload,
            "signature": signature,
            "processor": "CryptoService_v1"
        }
        
        # 动态构建回复事件名，实现“定向广播”
        reply_event = f"res:sign:{request_id}"
        self.api.emit(reply_event, result=response_data)
        self.api.log(f"已回复: {reply_event}")