# plugins/virus_sim.py
from interface import IPlugin
# import time

class Plugin(IPlugin):

    def start(self):
        self.api.log("病毒模拟器启动...")
        
        # 模拟操作
        self.api.log("正在扫描系统漏洞...")
        
        # 核心：通过 API 广播事件
        # 原代码: self.kernel.emit(...)
        self.api.emit("risk_alert", level="HIGH", message="检测到异常代码注入！")
        
        self.api.log("警报已发送。")

    def stop(self):
        self.api.log("模拟结束")