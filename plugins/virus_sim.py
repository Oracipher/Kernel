# plugins/virus_sim.py

from interface import Neuron
# import time

class Plugin(Neuron):
    def start(self):
        self.api.log("模拟病毒启动...")
        self.api.log("试图注入恶意代码...")
        
        # 试图通过 append 破坏受保护的 config (假设系统有这个key)
        self.api.append_data("version", "1.0-HACKED")
        
        # 触发事件
        self.api.impulse("risk_alert", level="HIGH", message="检测到 rootkit 注入！")

    def stop(self):
        self.api.log("模拟结束")