# plugins/security_monitor.py
from interface import IPlugin

class Plugin(IPlugin):

    def start(self):
        self.api.log("安保系统已启动，正在监听风险警告...")
        # 原代码: self.kernel.on(...)
        self.api.on("risk_alert", self.handle_alert)

    def stop(self):
        self.api.log("安保系统关闭")

    def handle_alert(self, level, message, **kwargs):
        """这是回调函数，当事件发生时被内核调用"""
        print(f"\n>>> [警报响了!] 级别: {level}")
        print(f">>> [详细信息] {message}")
        
        # 如果是高危警报，记录到 context 数据里
        if level == "HIGH":
            # 原代码: self.context["data"].append(...)
            # 这是一个危险操作，现在通过 API 的 append_data 来做
            self.api.append_data("data", f"Security Breach: {message}")