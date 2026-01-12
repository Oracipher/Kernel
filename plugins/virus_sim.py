# plugins/virus_sim.py
# import time

class Plugin:
    def __init__(self, context, kernel):
        self.context = context
        self.kernel = kernel

    def start(self):
        print("[Virus] 病毒模拟器启动...")
        
        # 模拟一个耗时操作，然后触发事件
        print("[Virus] 正在扫描系统漏洞...")
        # 注意：在真实开发中，不要在 start 里写死循环或太耗时的操作，会卡住主线程
        # 这里为了演示简单直接写了
        
        # 核心：广播事件！
        # 只要 security_monitor.py 已经加载，它就会收到这个消息
        self.kernel.emit("risk_alert", level="HIGH", message="检测到异常代码注入！")
        
        print("[Virus] 警报已发送。")

    def stop(self):
        print("[Virus] 模拟结束")