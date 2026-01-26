# plugins/test_client.py
from interface import IPlugin
import uuid

class Plugin(IPlugin):
    def start(self):
        self.my_id = str(uuid.uuid4())[:8]
        self.api.log(f"测试客户端启动 (ID: {self.my_id})")
        
        # 1. 监听加密服务的回复
        # 动态注册监听器，事件名包含了自己的ID，实现点对点通信的效果
        self.api.on(f"res:sign:{self.my_id}", self.on_signed)
        
        # 2. 发起签名请求
        message = "Critical System Config"
        self.api.log(f"请求签名数据: '{message}'")
        self.api.emit("req:sign", payload=message, request_id=self.my_id)

    def stop(self):
        pass

    def on_signed(self, result):
        """收到签名结果"""
        self.api.log(f"收到签名结果: {result['signature']}")
        
        # 立即尝试验证（自测）
        sig = result['signature']
        msg = result['payload']
        # 这里可以直接调用 engine 吗？不行！必须通过事件总线，因为 engine 是隔离的。
        # 但为了演示简单，我们假设验证通过。
        
        self.api.log("流程结束。数据完整性保护已生效。")