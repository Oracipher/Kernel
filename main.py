# main.py

import importlib.util
import os
import traceback

PLUGIN_DIR = "plugins"

plugin_context = {
    "version": "1.0",
    "admin": "Administrator",
    "data": []}
    # 允许插件继续补充相关数据
loaded_plugins = {}

def load_func(filename):
    """
    加载函数
    后置衔接load_confirmed_func()函数
    """
    path = os.path.join(PLUGIN_DIR, filename)
    name = filename.replace(".py", "")
    load_confirmed_func(filename, name, path)
    
def load_confirmed_func(filename, name, path):
    """
    加载确认，创建一个防火墙
    这是load_func()函数的后置
    """
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        run_func(mod, filename)
        print(f"[+] {filename} load successed")
        if hasattr(mod, "Plugin"):
            plugin_instance = mod.Plugin()
            loaded_plugins[name] = plugin_instance
            plugin_instance.start()
            print(f"[+] {name} already started")
        else:
            print(f"[*] {name} not have plugin class")
        
    except Exception as e:
        print(f"[-] {filename} load filed, because {e}")
        traceback.print_exc()

def run_func(mod, filename):
    """
    执行函数
    """
    if hasattr(mod, "main"):
        try:
            mod.main(plugin_context)
        except TypeError:
            # print(f"[*] {filename} is ignored (there is no main function)")
            print(f"[-] The {filename} interface is incorrect;")
            print("the main() function must accept one parameter.")
    
def init_plugins():
    """初始化：扫描并加载所有的插件"""
    if not os.path.exists(PLUGIN_DIR):
        os.makedirs(PLUGIN_DIR)
        
    print("[*] 系统正在初始化... ")
    for file in os.listdir(PLUGIN_DIR):
        if file.endswith(".py"):
            load_func(file)
    print("[+] 初始化成功\n")

if __name__ == "__main__":
    init_plugins()
    
    while True:
        cmd = input("Kernel> ").strip().lower()
        
        if cmd == "exit":
            print("正在关闭系统...")
            break
    
        elif cmd == "list":
            print(f"当前存活插件: {list(loaded_plugins.keys())}")
            
        elif cmd.startswith("stop "):
            # 这里需要修复
            # 假设中间存在多个空格
            # 则需要自动设置成一个空格
            name = cmd.split(" ")
            plugin = loaded_plugins.get(name)
            
            if plugin:
                try:
                    plugin.stop()
                    del loaded_plugins[name]
                    print(f"[-] 插件 {name} 已卸载")
                except Exception as e:
                    print(f"[!] 停止失败: {e}")
            else:
                print(f"[!] 找不到插件： {name}")
                
        elif cmd == "data":
            # 查看当前的共享上下文数据
            print(f"System Context: {plugin_context}")
        
        else:
            print("未知命令")


