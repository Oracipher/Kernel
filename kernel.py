# kernel_fixed.py

import os
import importlib
import importlib.util
import traceback

class PluginKernel:
    def __init__(self):
        # 1. 将全局变量改为类的属性（self.xxx）
        # 这样数据就属于这个内核实例，而不是飘在外面
        self.PLUGIN_DIR = "plugins"
        self.context = {
            "version": "1.0",
            "admin": "Administrator",
            "data": []
        }
        self.loaded_plugins = {}  # 存放实例化后的插件对象 {name: instance}
        self.loaded_modules = {}  # 存放原始模块对象 {name: module}

        # 确保目录存在
        if not os.path.exists(self.PLUGIN_DIR):
            os.makedirs(self.PLUGIN_DIR)

    def init_plugins_func(self):
        """启动时扫描并加载所有插件"""
        print("[*] 系统正在初始化...")
        for file in os.listdir(self.PLUGIN_DIR):
            if file.endswith(".py"):
                self.load_plugin_func(file)
        print("[+] 初始化成功\n")

    def load_plugin_func(self, filename):
        """加载单个插件的逻辑"""
        filename = os.path.basename(filename)
        name = os.path.splitext(filename)[0]
        path = os.path.join(self.PLUGIN_DIR, filename)

        try:
            # 动态导入的标准写法
            spec = importlib.util.spec_from_file_location(name, path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            # 必须保存模块对象，否则无法 reload
            self.loaded_modules[name] = mod

            # 检查并实例化插件
            if hasattr(mod, "Plugin"):
                # 将 self.context 传给插件
                plugin_instance = mod.Plugin(self.context)
                self.loaded_plugins[name] = plugin_instance
                plugin_instance.start()
                print(f"[+] {name} 加载并启动成功")
            else:
                print(f"[*] {name} 没有找到 Plugin 类")

        except Exception as e:
            print(f"[-] {filename} 加载失败: {e}")
            traceback.print_exc()

    def stop_plugin_func(self, name):
        """停止并卸载插件"""
        if name in self.loaded_plugins:
            try:
                plugin = self.loaded_plugins[name]
                plugin.stop() # 调用插件的 stop 方法
                del self.loaded_plugins[name] # 从内存移除实例
                print(f"[-] 插件 {name} 已卸载")
            except Exception as e:
                print(f"[!] 停止失败: {e}")
        else:
            print(f"[!] 找不到运行中的插件：{name}")

    def reload_plugin_func(self, name):
        """热重载逻辑"""
        # 1. 检查模块是否被加载过（基于 loaded_modules）
        if name not in self.loaded_modules:
            print(f"[!] 模块 {name} 未加载，请先使用 load 命令")
            return

        print(f"[*] 正在热重载：{name} ...")

        # 2. 停止旧实例
        if name in self.loaded_plugins:
            try:
                self.loaded_plugins[name].stop()
                del self.loaded_plugins[name]
            except Exception as e:
                print(f"[!] 旧实例停止异常: {e}")

        # 3. 核心：重载模块对象
        try:
            old_mod = self.loaded_modules[name]
            # importlib.reload 会强制 Python 重新读取文件更新内存中的代码
            new_mod = importlib.reload(old_mod) 
            self.loaded_modules[name] = new_mod # 更新引用

            # 4. 重新实例化
            if hasattr(new_mod, "Plugin"):
                new_instance = new_mod.Plugin(self.context)
                self.loaded_plugins[name] = new_instance
                new_instance.start()
                print(f"[+] {name} 热重载完成")
            else:
                print("[-] 重载后未发现 Plugin 类")
        except Exception as e:
            print(f"[-] 重载失败: {e}")
            traceback.print_exc()

    def list_plugins_func(self):
        return list(self.loaded_plugins.keys())

# --- 主程序入口 ---
if __name__ == "__main__":
    # 实例化内核
    kernel = PluginKernel()
    kernel.init_plugins_func()
    
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
                # 退出前最好停止所有插件
                for name in kernel.list_plugins_func():
                    kernel.stop_plugin_func(name)
                break
        
            elif cmd == "list":
                print(f"当前在线插件: {kernel.list_plugins_func()}")
                
            elif cmd == "stop":
                if arg:
                    kernel.stop_plugin_func(arg)
                else:
                    print("用法: stop <插件名>")
                    
            elif cmd == "reload":
                if arg:
                    kernel.reload_plugin_func(arg)
                else:
                    print("用法: reload <插件名>")
                
            elif cmd == "load":
                if arg:
                    kernel.load_plugin_func(arg)
                else:
                    print("用法: load <文件名.py>")
            
            elif cmd == "data":
                print(f"System Context: {kernel.context}")
            
            else:
                print("未知命令")
        except KeyboardInterrupt:
            print("\n强制退出")
            break