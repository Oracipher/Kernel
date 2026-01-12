import threading
import time

class Plugin:
    def __init__(self, context, kernel):
        self.kernel = kernel
        self._stop_event = threading.Event()

    def start(self):
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        print("[Scanner] 开始扫描...")
        while not self._stop_event.is_set():
            time.sleep(3)
            # 广播事件！我不需要知道 Logger 是谁，我只管喊
            self.kernel.emit("log", msg="扫描发现一个漏洞！", level="WARNING")

    def stop(self):
        self._stop_event.set()