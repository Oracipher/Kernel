
import time
class Plugin:
    def __init__(self, context):
        self.context = context
        self.name = "helloPlugin"
        
    def start(self):
        print("hello plugin already started")
        print(f"系统版本: {self.context['version']}")
        time.sleep(10)
        self.context['data'].append(f"{self.name}已上线")
        
    def stop(self):
        print("good by, hello plugin")
        