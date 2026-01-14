# interface.py

from abc import ABC, abstractmethod

class BaseModule(ABC):
    """
    插件接口基类
    所有的插件必须继承此类，
    并实现所有的@abcstractmethod装饰方法
    """
    
    def __init__(self, api):
        # 这里的context和kernel是内核注入近来的
        # self.context = context
        # self.kernel = kernel
        self.api = api
        
    @abstractmethod
    def start(self):
        """
        插件启动时的入口
        """
        pass
    
    @abstractmethod
    def stop(self):
        """
        插件停止/卸载是的清理逻辑
        """
        pass
    
    # def log(self, message):
    #     print(f"[{self.__class__.__name__}] {message}")
        
        