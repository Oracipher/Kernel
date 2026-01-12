class Plugin:
    def __init__(self, context, kernel):
        self.context = context
        self.kernel = kernel # 拿到了内核的引用
        
    def start(self):
        print("[Logger] 启动，开始监听 'log' 事件...")
        # 告诉内核：有人发 'log' 事件时，执行我的 save_log 函数
        self.kernel.on("log", self.save_log)

    def stop(self):
        pass

    def save_log(self, msg, level="INFO"):
        # 这是被动触发的
        print(f"【日志中心】 [{level}] {msg}")