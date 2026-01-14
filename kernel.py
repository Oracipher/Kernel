# kernel.py

import os
import importlib.util
import importlib
import traceback
import sys

from interface import BaseModule
from api import PluginAPI

class MicroKernel:
    def __init__(self):
        self.PLUGIN_DIR = "plugins"
        self.context = {
            "version": "1.0",
            "admin": "Administrator",
            "data": []
        }
        
        self.loaded_plugins = []
        self.loaded_modules = []
        self._events = {}
        
        if not os.path.exists(self.PLUGIN_DIR):
            os.makedirs(self.PLUGIN_DIR)
            
    def on(self, event_name: str, callback_func):
        """
        注册监听器：
        当event_name发生时，
        执行callback_func
        """
        if event_name not in self._events:
            self._events[event_name] = []
        self._events[event_name].append(callback_func)
        print(f"[system] 监听器已注册: {event_name} -> {callback_func.__name__}")
        
    def emit(self, event_name: str, **kwargs):
        """
        触发事件：
        广播给所有监听到这个事件的函数；
        """
        if event_name in self._events:
            for func in self._events[event_name]:
                try:
                    # 调用监听函数，把参数传递过去
                    func(**kwargs)
                except Exception as e:
                    print(f"[Error] 事件处理异常 ({event_name}): {e}")
                    traceback.print_exc()
                    
    # --- 核心逻辑炸弹 --- #
    
    def _check_and_start(self, mod, name):
        """
        检查模块中是否存在 Plugin 类并启动
        """
        if hasattr(mod, "Plugin"):
            try:
                plugin_api = PluginAPI(self, name)
                plugin_instance = mod.Plugin(plugin_api)
                if not isinstance(plugin_instance, BaseModule):
                    print(f"[warn] {name} 的 plugin 类没有继承interface.BaseModule")
                self.loaded_plugins[name] = plugin_instance
                plugin_instance.start()
                print(f"[success] {name} 加载并启动成功")
            except TypeError as e:
                print(f"[Error] {name} 加载失败： 未实现接口规范")
                print(f"错误信息： {e}")
            except Exception as e:
                print(f"[]")