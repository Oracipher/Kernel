# plugins/test_client.py
from interface import IPlugin
import uuid

class Plugin(IPlugin):
    def start(self):
        # 生成一个唯一的请求ID
        self.request_id = str(uuid.uuid4())[:8]
        self.api.log(f"客户端上线 (ID: {self.request_id})")
        
        # 1. 监听特定的回复频道
        # 对应 CryptoService 发出的 "res:sign:{request_id}"
        reply_channel = f"res:sign:{self.request_id}"
        self.api.on(reply_channel, self.handle_signature)
        
        # 2. 发起签名请求
        payload = "Core_System_Config_v2"
        self.api.log(f"请求签名: '{payload}'")
        self.api.emit("req:sign", payload=payload, request_id=self.request_id)

    def stop(self):
        pass

    def handle_signature(self, result):
        """处理回调"""
        # result 是一个字典，由 CryptoService 发送
        sig = result.get('signature')
        processor = result.get('processor')
        self.api.log(f"收到签名结果: {sig[:10]}... (By {processor})")
        self.api.log("业务流程完成。")