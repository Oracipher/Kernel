# interface.py

from abc import ABC,abstractmethod

class IPlugin(ABC):
    
    @abstractmethod
    def start(self) -> None:
        """实现启动"""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """用来停止"""
        pass
    