from interface import IPlugin

class Plugin(IPlugin):
    def start(self):
        self.api.log("安保系统启动，监听风险中...")
        # 注册监听
        self.api.on("risk_alert", self.handle_alert)

    def stop(self):
        self.api.log("安保系统关闭")

    def handle_alert(self, level, message, **kwargs):
        """事件回调"""
        print(f"\n>>> [警报] 级别: {level} | 内容: {message}")
        
        # 记录高危日志到数据中心
        if level == "HIGH":
            self.api.append_data("data", f"BREACH: {message}")
            self.api.log("已将入侵记录写入系统数据中心")