class Plugin:
    def __init__(self, context):
        self.context = context
        self.name = "workerPlugin"
        
    def start(self):
        print("worker plugin already started")
        print("data is being prepared...")
        self.data = "this is my status data"
        self.context['data'].append(f"{self.name}已经上线")
        
    def stop(self):
        print("worker plugin already stoped")
        
    def get_status(self):
        return self.data