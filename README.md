# Python Micro Kernel

## 想法

1. 使用类型提示信息type hints
   
```python
from types import ModuleType
from api import PluginAPI
from interface import IPlugin

    def _check_and_start(self, loaded_module: ModuleType, plugin_name: str):
        if hasattr(loaded_module, "Plugin"):
            try:
                plugin_api: PluginAPI = PluginAPI(self, plugin_name)

                plugin_instance = loaded_module.Plugin(plugin_api)

```

2. 或者注释多写一点，注释驱动
   
```python
def _check_and_start(self, mod, name):
        # mod (module): 就是那个 .py 文件
        # name: 就是那个文件的名字，比如 "hello"
        
        # 步骤 1: 看看文件里有没有写 class Plugin
        if hasattr(mod, "Plugin"):
            try:
                # 步骤 2: 准备 API (相当于给新员工配的工作手机)
                # 里面存了两个信息：1.我是谁(self/内核)，2.它是谁(name)
                plugin_api = PluginAPI(self, name)
                
                # 步骤 3: 实例化 (相当于正式招人入职)
                # mod.Plugin 是类(图纸)，加括号()变成实例(活人)
                # 把工作手机(api)塞给它
                plugin_instance = mod.Plugin(plugin_api)
                
                # 步骤 4: 身份检查 (防止有人混水摸鱼)
                # 必须是 IPlugin 的后代才能入职
                if not isinstance(plugin_instance, IPlugin):
                    print(f"警告: {name} 没按规矩写代码！")
                
                # 步骤 5: 存入花名册 (关键！否则以后找不到它了)
                self.loaded_plugins[name] = plugin_instance
                
                # 步骤 6: 按下启动按钮
                plugin_instance.start()
                
                print(f"[+] {name} 启动成功")

            except Exception as e:
                print(f"启动出错了: {e}")
```

3. 写一份中英文对照表

|英文代码|脑内中文翻译|形象理解|
|:---:|:---:|:---:|
|Kernel|核心 / 司令部|大脑，管所有事的。|
|Plugin|插件 / 小兵|干具体活的员工。|
|Context|环境 / 公告栏|大家都能看到的数据（字典）。|
|Emit|发射 / 广播|拿个大喇叭喊话：“出事啦！”|
|Handler|处理者|听到喇叭后，跑过来干活的那个函数。|
|Instance|实例 / 实体|活的东西。类(Class)是死图纸，Instance 是照着图纸造出来的活人。|


## 已实现


## 未实现

1. 依赖管理： 如果插件A依赖插件B的处理
2. 配置管理： 每个插件如何拥有自己独立的配置文件
3. 插件不应该只有一个文件，而允许为一个文件夹
4. 

