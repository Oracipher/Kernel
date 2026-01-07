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
    path = os.path.join("PLUGIN_DIR", filename)
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
        if hasattr(mod, "plugin"):
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

if not os.path.exists(PLUGIN_DIR):
    os.makedirs(PLUGIN_DIR)

for file in os.listdir(PLUGIN_DIR):
    if file.endswith(".py"):
        load_func(file)
        print("\n --- system running --- ")
        print("current online plugins:\n")
        print(f"{list(loaded_plugins.keys())}")
        
