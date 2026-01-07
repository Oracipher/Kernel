# interface.py

import abc

class BaseModule(abc.ABC):
    def __init__(self, kernle_context):
        self.context = kernle_context
        self.name = self.__class__.__name__
        self._is_running = False
    
    @abc.abstractmethod
    def on_load(self):
        pass
    
    @abc.abstractmethod
    def on_start(self):
        pass
    
    @abc.abstractmethod
    def on_stop(self):
        pass
    
    def on_unload(self):
        print(f" >> [System] {self.name} resource recycling ...")
        