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
loaded_modules = {}

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
        
        loaded_modules[name] = mod
        # run_func(mod, filename)
        # print(f"[+] {filename} load successed")

        if hasattr(mod, "Plugin"):
            plugin_instance = mod.Plugin(plugin_context)
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
            try:
                # 这里需要修复
                # 假设中间存在多个空格
                # 则需要自动设置成一个空格
                name = cmd.split(" ", 1)[1].strip()
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
            except IndexError:
                print("[!] 语法错误")
                
        elif cmd.startswith("reload "):
            try:
                name = cmd.split(" ", 1)[1].strip()
                
                # 1. 检查是否加载过
                if name not in loaded_modules:
                    print(f"[!] 模块 {name} 未加载")
                    print("请使用load命令")
                    continue
                
                print(f"[*] 正在热重载： {name} ...")
                
                # 2. 停止就的插件实例
                # 如果不停止，就的线程可能还在进行，变成僵尸
                if name in loaded_plugins:
                    try:
                        old_plugin = loaded_plugins[name]
                        old_plugin.stop()
                        del loaded_plugins[name] # 从内存中移除旧的实例
                    except Exception as e:
                        print(f"[!] 停止旧实例失败者: {e}")
                
                # 3. 强制重载模块对象
                # 这会重新读取 .py 文件，更新内存中的类定义
                mod = loaded_modules[name]
                new_mod = importlib.reload(mod)
                loaded_modules[name] = new_mod
                # 更新模块引用
                
                # 4. 重新实例化并启动
                if hasattr(new_mod, "Plugin"):
                    new_instance = new_mod.Plugin(plugin_context)
                    loaded_plugins[name] = new_instance
                    new_instance.start()
                    print(f"[+] {name} 热重载完成")
                    
            except IndexError:
                print("[!] 用法： reloaded <插件名>")
            
            except Exception as e:
                print(f"[-] 重载失败： {e}")
                traceback.print_exc()
                
        elif cmd == "data":
            # 查看当前的共享上下文数据
            print(f"System Context: {plugin_context}")
            
        elif cmd.startswith("load "):
            try:
                filename = cmd.split(" ", 1)[1].strip()
                load_func(filename)
            except IndexError:
                print("[!] 用法： load <filename.py>")
        
        else:
            print("未知命令")
