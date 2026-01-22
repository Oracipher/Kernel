# kernel.py
import os
import importlib
import importlib.util
import traceback
import sys
from interface import IPlugin  # 现在 interface.py 里确实有 IPlugin 了
from api import PluginAPI

class PluginKernel:
    def __init__(self):
        self.PLUGIN_DIR = "plugins"
        # 全局上下文数据中心
        self.context = {
            "version": "1.0",
            "admin": "Administrator",
            "data": []  # 用于 security_monitor 存储警报
        }
        self.loaded_plugins = {} 
        self.loaded_modules = {}
        self._events = {}
        
        if not os.path.exists(self.PLUGIN_DIR):
            os.makedirs(self.PLUGIN_DIR)
    
    def on(self, event_name: str, callback_func):
        if event_name not in self._events:
            self._events[event_name] = []
        self._events[event_name].append(callback_func)
        # print(f"[System] 监听器已注册: {event_name} -> {callback_func.__name__}")
        
    def emit(self, event_name: str, **kwargs):
        if event_name in self._events:
            for func in self._events[event_name]:
                try:
                    func(**kwargs)
                except Exception as e:
                    print(f"[!] 事件处理异常 ({event_name}): {e}")
                    traceback.print_exc()

    def _check_and_start(self, mod, name):
        """检查模块是否有 Plugin 类并启动"""
        if hasattr(mod, "Plugin"):
            try:
                # 1. 创建 API 实例
                plugin_api = PluginAPI(self, name)
                # 2. 实例化插件，注入 API
                plugin_instance = mod.Plugin(plugin_api)
                
                # 3. 检查类型继承
                if not isinstance(plugin_instance, IPlugin):
                    print(f"[!] 警告: {name} 未继承 interface.IPlugin，可能会运行出错")
                
                self.loaded_plugins[name] = plugin_instance
                plugin_instance.start()
                print(f"[+] {name} 就绪")
            except TypeError as e:
                print(f"[!] {name} 加载失败：接口签名不匹配")
                print(f"详情： {e}")
                traceback.print_exc()
            except Exception as e:
                print(f"[!] {name} 启动异常： {e}")
                traceback.print_exc()
        else:
            print(f"[*] {name} 忽略：未找到 Plugin 类")

    def _load_action(self, filename, name, path):
        try:
            spec = importlib.util.spec_from_file_location(name, path)
            mod = importlib.util.module_from_spec(spec) # type:ignore
            sys.modules[name] = mod 
            spec.loader.exec_module(mod)# type: ignore
            
            self.loaded_modules[name] = mod
            self._check_and_start(mod, name)
        except Exception as e:
            print(f"[-] {filename} 加载失败: {e}")

    def init_plugins(self):
        print("[*] 系统正在初始化...")
        # 确保目录存在
        if not os.path.exists(self.PLUGIN_DIR):
            os.makedirs(self.PLUGIN_DIR)
            
        for file in os.listdir(self.PLUGIN_DIR):
            if file.endswith(".py"):
                self.load_plugin(file)
        print("[+] 初始化完成\n")

    def load_plugin(self, filename):
        filename = os.path.basename(filename)
        name = os.path.splitext(filename)[0]
        path = os.path.join(self.PLUGIN_DIR, filename)
        self._load_action(filename, name, path)

    def stop_plugin(self, name):
        if name in self.loaded_plugins:
            try:
                print(f"[*] 正在停止 {name}...")
                self.loaded_plugins[name].stop()
                del self.loaded_plugins[name]
                print(f"[-] {name} 已卸载")
            except Exception as e:
                print(f"[!] 停止失败: {e}")
        else:
            print(f"[!] 未找到运行中的插件：{name}")

    def reload_plugin(self, name):
        if name not in self.loaded_modules:
            print(f"[!] 模块 {name} 未加载，请先使用 load 命令")
            return

        print(f"[*] 正在热重载：{name} ...")
        if name in self.loaded_plugins:
            self.stop_plugin(name)

        try:
            old_mod = self.loaded_modules[name]
            new_mod = importlib.reload(old_mod)
            self.loaded_modules[name] = new_mod
            self._check_and_start(new_mod, name)
            print(f"[+] {name} 热重载完毕")
        except Exception as e:
            print(f"[-] 重载失败: {e}")
            traceback.print_exc()

    def list_plugins(self):
        return list(self.loaded_plugins.keys())

# --- 主程序入口 ---
if __name__ == "__main__":
    kernel = PluginKernel()
    kernel.init_plugins()
    
    print("支持命令: list, load <file>, stop <name>, reload <name>, data, exit")
    
    while True:
        try:
            cmd_str = input("Kernel> ").strip()
            if not cmd_str:
                continue
            
            parts = cmd_str.split(" ", 1)
            cmd = parts[0].lower()
            arg = parts[1].strip() if len(parts) > 1 else None

            if cmd == "exit":
                print("正在关闭系统...")
                # 复制 keys 列表以防遍历时字典改变
                for name in list(kernel.loaded_plugins.keys()):
                    kernel.stop_plugin(name)
                break
            elif cmd == "list":
                print(f"在线插件: {kernel.list_plugins()}")
            elif cmd == "stop":
                if arg:
                    kernel.stop_plugin(arg)
                else:
                    print("用法: stop <插件名>")
            elif cmd == "reload":
                if arg:
                    kernel.reload_plugin(arg)
                else:
                    print("用法: reload <插件名>")
            elif cmd == "load":
                if arg:
                    kernel.load_plugin(arg)
                else:
                    print("用法: load <文件名.py>")
            elif cmd == "data":
                import json
                # 格式化打印 context 数据，方便查看
                print(json.dumps(kernel.context, indent=2, ensure_ascii=False))
            else:
                print("未知命令")
        except KeyboardInterrupt:
            print("\n强制退出")
            break
        except Exception as e:
            print(f"系统错误: {e}")