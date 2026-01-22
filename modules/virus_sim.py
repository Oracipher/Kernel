from interface import IPlugin

class Plugin(IPlugin):
    def start(self):
        self.api.log("模拟病毒启动...")
        self.api.log("试图注入恶意代码...")
        
        # 触发事件，测试 security_monitor 是否能收到
        self.api.emit("risk_alert", level="HIGH", message="检测到 rootkit 注入！")

    def stop(self):
        self.api.log("模拟结束")