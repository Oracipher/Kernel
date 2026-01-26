# interface.py

from abc import ABC, abstractmethod

class Root(ABC):
    """
    基类接口
    """
    
    def __init__(self, api):
        # 接收内核注入的 API 实例
        self.api = api
        
    @abstractmethod
    def start(self):
        """插件启动时的入口"""
        pass
    
    @abstractmethod
    def stop(self):
        """插件停止/卸载时的清理逻辑"""
        pass