# kernel.py
import os
import importlib
import importlib.util
import traceback
import sys

class PluginKernel:
    def __init__(self):
        self.PLUGIN_DIR = "plugins"
        self.context = {
            "version": "1.0",
            "admin": "Administrator",
            "data": []
        }
        self.loaded_plugins = {} 
        self.loaded_modules = {}
        self._events = {}
        
        if not os.path.exists(self.PLUGIN_DIR):
            os.makedirs(self.PLUGIN_DIR)
    
    def on(self, event_name: str, callback_func):
        """注册监听器：
        当event_name发生的时候，执行callback_func
        """
        if event_name not in self._events:
            self._events[event_name] = []
        self._events[event_name].append(callback_func)
        print(f"[System] 监听器已注册: {event_name} -> {callback_func.__name__}")
        
    def emit(self, event_name: str, **kwargs):
        """触发事件：广播给所有监听这个事件的函数
        kwargs: 允许传递任意参数
        """
        if event_name in self._events:
            for func in self._events[event_name]:
                try:
                    # 调用监听者的函数，把参数传递过去
                    func(**kwargs)
                except Exception as e:
                    print(f"[!] 事件处理异常 ({event_name}): {e}")
    
    # --- 内部核心逻辑 (通常建议加下划线前缀表示这是内部用的) ---

    def _check_and_start(self, mod, name):
        """检查模块是否有 Plugin 类并启动"""
        if hasattr(mod, "Plugin"):
            # 传参：name 必须从外部传进来
            plugin_instance = mod.Plugin(self.context, self)
            self.loaded_plugins[name] = plugin_instance
            plugin_instance.start()
            print(f"[+] {name} 加载并启动成功")
        else:
            print(f"[*] {name} 忽略：未找到 Plugin 类")

    def _load_action(self, filename, name, path):
        """实际执行加载的动作"""
        try:
            spec = importlib.util.spec_from_file_location(name, path)
            mod = importlib.util.module_from_spec(spec)
            
            # 这是一个好习惯：放入 sys.modules 以支持标准 import
            sys.modules[name] = mod 
            
            spec.loader.exec_module(mod)

            self.loaded_modules[name] = mod
            # 修正：调用内部方法要用 self.method，并把 name 传过去
            self._check_and_start(mod, name)

        except Exception as e:
            print(f"[-] {filename} 加载失败: {e}")
            traceback.print_exc()

    # --- 对外公开接口 ---

    def init_plugins(self):
        """启动时扫描"""
        print("[*] 系统正在初始化...")
        for file in os.listdir(self.PLUGIN_DIR):
            if file.endswith(".py"):
                self.load_plugin(file)
        print("[+] 初始化成功\n")

    def load_plugin(self, filename):
        """加载命令入口"""
        filename = os.path.basename(filename)
        name = os.path.splitext(filename)[0]
        path = os.path.join(self.PLUGIN_DIR, filename)
        
        # 修正：使用 self 调用
        self._load_action(filename, name, path)

    def stop_plugin(self, name):
        """停止命令入口"""
        if name in self.loaded_plugins:
            try:
                print(f"[*] 正在停止 {name}...")
                self.loaded_plugins[name].stop()
                del self.loaded_plugins[name]
                print(f"[-] 插件 {name} 已卸载")
            except Exception as e:
                print(f"[!] 停止失败: {e}")
        else:
            print(f"[!] 找不到运行中的插件：{name}")

    def reload_plugin(self, name):
        """重载命令入口"""
        if name not in self.loaded_modules:
            print(f"[!] 模块 {name} 未加载，请先使用 load 命令")
            return

        print(f"[*] 正在热重载：{name} ...")

        # 1. 如果插件正在运行，先停止它
        # 直接调用类内部的 stop_plugin 方法即可，不用拆得太碎
        if name in self.loaded_plugins:
            self.stop_plugin(name)

        # 2. 执行重载核心逻辑
        try:
            old_mod = self.loaded_modules[name]
            # 重新编译代码
            new_mod = importlib.reload(old_mod)
            self.loaded_modules[name] = new_mod
            
            # 3. 重新检查并启动
            self._check_and_start(new_mod, name)
            print(f"[+] {name} 热重载流程结束")

        except Exception as e:
            print(f"[-] 重载失败: {e}")
            traceback.print_exc()

    def list_plugins(self):
        return list(self.loaded_plugins.keys())

# --- 主程序 ---
if __name__ == "__main__":
    kernel = PluginKernel()
    kernel.init_plugins()
    
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
                for name in kernel.list_plugins():
                    kernel.stop_plugin(name)
                break
            elif cmd == "list":
                print(f"当前在线插件: {kernel.list_plugins()}")
            elif cmd == "stop":
                if arg:
                    kernel.stop_plugin(arg) # 这里的 kernel 是实例名
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
                print(f"Context: {kernel.context}")
            else:
                print("未知命令")
        except KeyboardInterrupt:
            break