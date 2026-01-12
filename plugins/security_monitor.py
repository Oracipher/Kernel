# plugins/security_monitor.py

class Plugin:
    def __init__(self, context, kernel):
        self.context = context
        self.kernel = kernel

    def start(self):
        # 注册监听器：当有人发出 'risk_alert' 事件时，执行 self.handle_alert
        print("[Monitor] 安保系统已启动，正在监听风险警告...")
        self.kernel.on("risk_alert", self.handle_alert)

    def stop(self):
        print("[Monitor] 安保系统关闭")

    def handle_alert(self, level, message, **kwargs):
        """这是回调函数，当事件发生时被内核调用"""
        print(f"\n>>> [警报响了!] 级别: {level}")
        print(f">>> [详细信息] {message}")
        
        # 如果是高危警报，我们甚至可以强制记录到 context 数据里
        if level == "HIGH":
            self.context["data"].append(f"Security Breach: {message}")