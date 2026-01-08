# worker.py

import threading

class Plugin:
    def __init__(self, context):
        self.context = context
        self.name = "workerPlugin"
        self._is_running = False
        self._thread = None
        
    def start(self):
        print(f"[{self.name}] 正在启动后台线程...")
        self._is_running = True
        
        # 创建一个线程
        # 目标是执行self.run_logic
        self._thread = threading.Thread(target = self.run_logic)
        # daemon = True 表示如果你强行关闭主程序
        # 这个线程也会跟着一起死亡
        self._thread.daemon = True
        self._thread.start()
        print(f"[{self.name}] 启动成功")
        
        # print("worker plugin already started")
        # print("data is being prepared...")
        # time.sleep(10)
        # self.data = "this is my status data"
        # self.context['data'].append(f"{self.name}已经上线")
        
    def stop(self):
        print(f"[{self.name}] 收到停止信号...")
        # 1. 修改开关
        # 让run_logic里的while循环结束
        self._is_running = False
        
        if self._thread:
            self._thread.join(timeout = 3.0) # 最多等待3秒
        print("worker plugin already stoped")
        
    def get_status(self):
        return self.data