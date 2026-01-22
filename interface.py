# interface.py

from abc import ABC,abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api import PluginAPI

class IPlugin(ABC):
    """插件接口基类"""
    def __init__(self, api: 'PluginAPI') -> None:
        self.api = api
    
    @abstractmethod
    def start(self) -> None:
        """实现启动"""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """用来停止"""
        pass
    