# kernel.py

import os
import importlib
import importlib.util
import traceback
import sys
import json

from interface import Root
from api import Omni

class MicroKernel:
    
    def __init__(self):
        self.PLUGIN_DIR = "plugins"
        self.context = {
            "version": "1.0",
            "admin": "Administrator",
            "data": []  # 用于 security_monitor 存储警报
        }
        self.loaded_plugins = {} # 存储实例化后的插件对象: {name: instance}
        self.loaded_modules = {} # 存储模块对象: {name: module}
        self.plugin_paths = {}   # 存储插件路径用于重载: {name: path}
        self._events = {}        # 事件总线
        
        if not os.path.exists(self.PLUGIN_DIR):
            os.makedirs(self.PLUGIN_DIR)
            
    def monitor(self, event_name: str, callback_func):
        """Register an event listener"""
        if event_name not in self._events:
            self._events[event_name] = []
        self._events[event_name].append(callback_func)
        print("[System] Listener registered:")
        print(f" {event_name} -> {callback_func.__name__}")
        
    def emit(self, event_name:str, **kwargs):
        """Broadcast an event to all listeners"""
        if event_name in self._events:
            for func in self._events[event_name]: 
                try:
                    func(**kwargs)
                except Exception as e:
                    print(f"[!] Event handling error ({event_name}): {e}")
                    traceback.print_exc()
                        
    # --- Loader Mechanism --- #
    
    def _bootstrap(self, mod, name):
        """Check if the module has a Plugin class and start it"""
        if hasattr(mod, "Plugin"):
            try:
                # 1. Create API instance
                plugin_api = Omni(self, name)
                # 2. Instantiate the plugin, injecting the API
                plugin_instance = mod.Plugin(plugin_api)
                
                # 3. Check type inheritance
                if not isinstance(plugin_instance, Root):
                    print(f"[!] Error: {name} does not inherit from interface.")
                    print("Root, potential runtime issues.")
                    
                self.loaded_plugins[name] = plugin_instance
                plugin_instance.start()
                print(f"[+] {name} is ready")
            except TypeError as e:
                print(f"[!] {name} failed to load: interface signature mismatch")
                print(f"Details: {e}")
                traceback.print_exc()
            except Exception as e:
                print(f"[!] {name} failed to load: {e}")
                traceback.print_exc()
        else:
            print(f"[*] {name} does not have a Plugin class, skipping.")
            
    def _action_loader(self, filename, name, path):
        """Dynamically load a plugin module from file"""
        try:
            # get spec
            spec = importlib.util.spec_from_file_location(name,path)
            if spec is None:
                print(f"[-] Error: could not load spec for {filename}")
                print("file not found or invalid module.")
                return
            
            if spec.loader is None:
                print(f"[-] Error: no loader available for {filename}")
                return
            
            # create module from spec
            mod = importlib.util.module_from_spec(spec)
            # insert into sys.modules
            sys.modules[name] = mod
            # execute the module
            spec.loader.exec_module(mod)
            # store module reference
            self.loaded_modules[name] = mod
            self.plugin_paths[name] = path
            # bootstrap the plugin
            self._bootstrap(mod, name)
        except Exception as e:
            print(f"[-] Failed to load {filename}: {e}")
            traceback.print_exc()
            
    # --- Public Methods --- #

    def init_plugins(self):
        """Initialize all plugins in the plugin directory"""
        print(f"[*] Scanning {self.PLUGIN_DIR}...")
        for filename in os.listdir(self.PLUGIN_DIR):
            if filename.endswith(".py"):
                name = os.path.splitext(filename)[0]
                path = os.path.join(self.PLUGIN_DIR, filename)
                self._action_loader(filename, name, path)
                
    def load_plugin(self, filename):
        # filename = os.path.basename(filename)
        if not filename.endswith(".py"):
            filename += ".py"
        name = os.path.splitext(filename)[0]
        path = os.path.join(self.PLUGIN_DIR, filename)
        if not os.path.exists(path):
            print(f"[!] File not found: {path}")
            return
        self._action_loader(filename, name, path)
        
    def stop_plugin(self, name):
        """Stop and unload a plugin by name"""
        if name in self.loaded_plugins:
            try:
                self.loaded_plugins[name].stop()
            except Exception as e:
                print(f"[!] Error stopping {name}: {e}")
            
            # 清理引用
            del self.loaded_plugins[name]
            if name in self.loaded_modules:
                del self.loaded_modules[name]
                
            print(f"[+] {name} stopped.")
        else:
            print(f"[!] Plugin {name} is not running.")
            
    def reload_plugin(self, name):
        """Reload a plugin by name"""
        # 1. 保存路径 (因为 stop_plugin 会清理 loaded_modules，但我们需要路径重新加载)
        path = self.plugin_paths.get(name)
        
        # 2. 只有当插件曾经被加载过，且我们知道它在哪里时才重载
        if not path:
            # 尝试从 loaded_modules 逆推，或者直接报错
            # 
            print(f"[!] Cannot reload {name}: path unknown.")
            return

        # 3. 停止旧实例
        if name in self.loaded_plugins:
            self.stop_plugin(name)
            
        # 4. 重新加载 (像新文件一样加载)
        print(f"[*] Reloading {name} from {path}...")
        filename = os.path.basename(path)
        self._action_loader(filename, name, path)

    def list_plugins(self):
        return list(self.loaded_plugins.keys())
        
if __name__ == "__main__":
    kernel = MicroKernel()
    kernel.init_plugins()
    
    print("\n === Kernel Shell === ")
    # print("Commands: list, load <file>, stop <name>, reload <name>, data, exit")
    
    while True:
        try:
            cmd_str = input("kernel> ").strip()
            if not cmd_str:
                continue
            parts = cmd_str.split()
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else None
            
            if cmd == "exit":
                print("Shutting down...")
                # 复制 keys 列表以防遍历时字典改变
                for name in list(kernel.loaded_plugins.keys()):
                    kernel.stop_plugin(name)
                break
            elif cmd == "list":
                print(f"Active Plugins: {kernel.list_plugins()}")
            elif cmd == "stop":
                if arg:
                    kernel.stop_plugin(arg)
                else:
                    print("Usage: stop <plugin_name>")
            elif cmd == "reload":
                if arg:
                    kernel.reload_plugin(arg)
                else:
                    print("Usage: reload <plugin_name>")
            elif cmd == "load":
                if arg:
                    kernel.load_plugin(arg)
                else:
                    print("Usage: load <filename.py>")
            elif cmd == "data":
                # 格式化打印 context 数据，方便查看
                print(json.dumps(kernel.context, indent=2, ensure_ascii=False))
            else:
                print("Unknown command.")
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"[!] Error: {e}")
            traceback.print_exc()
            