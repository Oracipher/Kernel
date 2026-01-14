# interface.py
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api import PluginAPI

class IPlugin(ABC):
    """
    插件接口基类
    """
    def __init__(self, api: 'PluginAPI') -> None:
        self.api = api
        
    @abstractmethod
    def start(self) -> None:
        """插件启动入口"""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """插件停止清理"""
        pass