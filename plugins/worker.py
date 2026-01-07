class Plugin:
    def start(self):
        print("worker plugin already started")
        print("data is being prepared...")
        self.data = "this is my status data"
        
    def stop(self):
        print("worker plugin already stoped")
        
    def get_status(self):
        return self.data