# kernel.py

import os
import importlib
import importlib.util
import traceback
import sys
import json

# [Mentor Note] 移除 sys.path.append(os.getcwd()) 
# 这通常是不安全的，且如果运行目录正确，这行是多余的。

from interface import IPlugin  # 修正引用名称 Root -> IPlugin
from api import Omni

class MicroKernel:
    
    def __init__(self):
        self.PLUGIN_DIR = "plugins"
        # 全局上下文数据
        self.context = {
            "version": "1.0",
            "admin": "Administrator",
            "data": []  # 用于 security_monitor 存储警报
        }
        self.loaded_plugins = {} # {name: instance}
        self.loaded_modules = {} # {name: module}
        self.plugin_paths = {}   # {name: path}
        self._events = {}        # 事件总线
        
        if not os.path.exists(self.PLUGIN_DIR):
            os.makedirs(self.PLUGIN_DIR)
            print(f"[*] Created plugin directory: {self.PLUGIN_DIR}")
            
    def monitor(self, event_name: str, callback_func):
        """Register an event listener"""
        if event_name not in self._events:
            self._events[event_name] = []
        self._events[event_name].append(callback_func)
        
    def emit(self, event_name:str, **kwargs):
        """Broadcast an event to all listeners"""
        if event_name in self._events:
            # [Mentor Note] 复制列表进行迭代，防止回调函数内部修改监听列表导致 Crash
            listeners = self._events[event_name][:] 
            for func in listeners: 
                try:
                    func(**kwargs)
                except Exception as e:
                    print(f"[!] Event error ({event_name}): {e}")
                    traceback.print_exc()
                        
    # --- Loader Mechanism --- #
    
    def _bootstrap(self, mod, name):
        """Check if the module has a Plugin class and start it"""
        if hasattr(mod, "Plugin"):
            try:
                # 1. Create API instance
                plugin_api = Omni(self, name)
                # 2. Instantiate the plugin
                plugin_instance = mod.Plugin(plugin_api)
                
                # 3. Check type inheritance
                if not isinstance(plugin_instance, IPlugin):
                    print(f"[!] Error: {name} does not inherit from IPlugin.")
                    return
                    
                self.loaded_plugins[name] = plugin_instance
                plugin_instance.start()
                print(f"[+] {name} is ready")
            except Exception as e:
                print(f"[!] '{name}' failed to bootstrap: {e}")
                traceback.print_exc()
        else:
            print(f"[*] Module '{name}' has no 'Plugin' class, skipping.")
            
    def _action_loader(self, filename, name, path):
        """Dynamically load a plugin module from file"""
        try:
            spec = importlib.util.spec_from_file_location(name, path)
            
            # [Mentor Note] 致命错误修复！
            # 原代码 `if spec is None or spec:` 会导致所有成功加载的模块也被判定为错误。
            if spec is None or spec.loader is None:
                print(f"[-] Error: Could not load spec for {filename}")
                return
            
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod
            spec.loader.exec_module(mod)
            
            self.loaded_modules[name] = mod
            self.plugin_paths[name] = path
            self._bootstrap(mod, name)
        except Exception as e:
            print(f"[-] Failed to load {filename}: {e}")
            traceback.print_exc()
            
    # --- Public Methods --- #

    def init_plugins(self):
        """Initialize all plugins in the plugin directory"""
        print(f"[*] Scanning {self.PLUGIN_DIR}...")
        
        if not os.path.exists(self.PLUGIN_DIR):
            print(f"[!] Plugin directory '{self.PLUGIN_DIR}' does not exist.")
            return
        
        for filename in os.listdir(self.PLUGIN_DIR):
            if filename.endswith(".py"):
                name = os.path.splitext(filename)[0]
                path = os.path.join(self.PLUGIN_DIR, filename)
                self._action_loader(filename, name, path)
                
    def load_plugin(self, filename):
        if not filename.endswith(".py"):
            filename += ".py"
        name = os.path.splitext(filename)[0]
        path = os.path.join(self.PLUGIN_DIR, filename)
        
        if not os.path.exists(path):
            print(f"[!] File not found: {path}")
            return
        
        if name in self.loaded_plugins:
            print(f"[!] Plugin {name} is already loaded.")
            return
        
        self._action_loader(filename, name, path)
        
    def stop_plugin(self, name):
        """Stop and unload a plugin by name"""
        if name in self.loaded_plugins:
            try:
                self.loaded_plugins[name].stop()
            except Exception as e:
                print(f"[!] Error stopping {name}: {e}")
            
            del self.loaded_plugins[name]
            
            # 清理 sys.modules
            if name in sys.modules:
                del sys.modules[name]
            
            # [Mentor Note] 修复：不要删除 loaded_modules 和 plugin_paths 中的记录
            # 否则 reload_plugin 找不到路径。
            # if name in self.loaded_modules: ... (Removed)
                
            print(f"[-] Plugin '{name}' stopped and unloaded.")
        else:
            print(f"[!] Plugin {name} is not running.")
            
    def reload_plugin(self, name):
        """Reload a plugin by name"""
        # 1. 获取路径
        path = self.plugin_paths.get(name)
        
        if not path:
            print(f"[!] Cannot reload '{name}': Path unknown or never loaded.")
            return
        
        print(f"[*] Reloading plugin '{name}'...")

        # 2. 停止旧实例
        if name in self.loaded_plugins:
            self.stop_plugin(name)
            
        # 3. 重新加载
        filename = os.path.basename(path)
        self._action_loader(filename, name, path)

    def list_plugins(self):
        return list(self.loaded_plugins.keys())
        
if __name__ == "__main__":
    kernel = MicroKernel()
    kernel.init_plugins()
    
    print("\n === Kernel Shell (Secured) === ")
    print("Type 'help' for summary, or '<command> -h' for details.")
    
    # [Mentor Strategy] 数据驱动：定义命令详细手册
    # 这样不仅代码整洁，而且修改文档不需要动逻辑代码
    CMD_MANUAL = {
        "list": "\n[usage] list\n[describe] 列出当前所有已加载到内存中的插件名称。",
        "load": "\n[usage] load <filename>\n[describe] 从 plugins 目录加载新插件。\n[example] load my_plugin(无需输入 .py)",
        "reload": "\n[usage] reload <name>\n[describe]] 热重载插件。先停止旧实例，再重新读取代码并启动。\n[attention] 这里的 name 是插件名(如 hello_info),不是文件名。",
        "stop": "\n[usage] stop <name>\n[describe] 调用插件的 stop() 方法并将其从内存卸载。",
        "data": "\n[usage] data\n[describe] 以 JSON 格式打印当前的全局上下文数据(Context)。",
        "exit": "\n[usage] exit\n[describe] 停止所有插件并退出内核进程。",
        "cls": "\n[usage] cls / clear\n[describe] 清空终端屏幕。",
    }

    while True:
        try:
            cmd_str = input("kernel> ").strip()
            if not cmd_str:
                continue
            
            parts = cmd_str.split()
            cmd = parts[0].lower()
            
            # 获取参数列表，如果没有参数则为空列表
            # [Mentor Note] 这是一个更健壮的参数解析方式
            args = parts[1:] 
            
            # === [核心逻辑] 全局帮助拦截器 ===
            # 检测用户是否在请求帮助 (e.g., "list -h", "load --help")
            if args and args[0] in ["-h", "--help"]:
                if cmd in CMD_MANUAL:
                    print(CMD_MANUAL[cmd])
                else:
                    print(f"No manual entry for '{cmd}'")
                continue # 拦截结束，不再执行后续逻辑
            # ==============================

            # --- 命令分发 ---
            
            if cmd == "exit":
                print("Shutting down...")
                for name in list(kernel.loaded_plugins.keys()):
                    kernel.stop_plugin(name)
                break
                
            elif cmd in ["help", "?"]:
                print("Available Commands:", ", ".join(CMD_MANUAL.keys()))
                print("Try 'load --help' for specific info.")

            elif cmd in ["cls", "clear"]:
                os.system('cls' if os.name == 'nt' else 'clear')

            elif cmd == "list":
                print(f"Active Plugins: {kernel.list_plugins()}")
                
            elif cmd == "stop":
                if args:
                    kernel.stop_plugin(args[0])
                else:
                    print("Error: Missing argument. Try 'stop -h'")

            elif cmd == "reload":
                if args:
                    target = args[0]
                    # 自动去除 .py 后缀，提升体验
                    if target.endswith(".py"):
                        target = target[:-3]
                    kernel.reload_plugin(target)
                else:
                    print("Error: Missing argument. Try 'reload -h'")

            elif cmd == "load":
                if args:
                    kernel.load_plugin(args[0])
                else:
                    print("Error: Missing filename. Try 'load -h'")
            
            elif cmd == "data":
                print(json.dumps(kernel.context, indent=2, ensure_ascii=False, default=str))
                
            else:
                print(f"Unknown command: '{cmd}'. Type 'help' for list.")
                
        except KeyboardInterrupt:
            print("\nForce Exiting...")
            break
        except Exception as e:
            print(f"[!] Shell Error: {e}")