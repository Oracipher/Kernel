from interface import IPlugin
# import time

class Plugin(IPlugin):
    def start(self):
        self.api.log("测试者上线，准备生成审计日志...")
        
        # 1. 模拟登录操作
        self.api.emit("audit:record", event_type="LOGIN", message="Admin user login from 192.168.1.1")
        
        # 2. 模拟敏感操作
        self.api.emit("audit:record", event_type="DATA_ACCESS", message="User accessed /etc/passwd")
        
        # 3. 查询结果
        self.api.log("正在请求审计记录...")
        self.api.emit("audit:query", limit=3)

    def stop(self):
        pass