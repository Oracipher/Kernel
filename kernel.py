# kernel.py

import os
import importlib.util
import sys

PLUGIN_DIR = "plugins"

def load_and_run_plugins():
    print("---内核启动：开始扫描插件---")
    
    if not os.path.exists(PLUGIN_DIR):
        print("---没有找到plugins文件夹---")
        return
    
    for folder_name in os.listdir(PLUGIN_DIR):
        plugin_path = os.path.join(PLUGIN_DIR, folder_name)
        
        