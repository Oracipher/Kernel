# interface.py

from abc import ABC, abstractmethod

class Neuron(ABC):
    """
    插件基类接口 (Protocol)
    强制所有插件必须实现标准生命周期方法
    """
    
    def __init__(self, api):
        # 接收内核注入的 API 实例
        self.api = api
        
    @abstractmethod
    def start(self) -> None:
        """插件启动时的入口"""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """插件停止/卸载时的清理逻辑"""
        pass