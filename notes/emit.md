
# emit function

---

在`virus_sim.py`插件中有这一行代码:
```python
self.api.emit("risk_alert",
level = "HIGH",
message = "检测到rootket注入"
)
```
其中的`lervel = "HIGH",message="...",`
就是传入`kernel`文件中`emit`函数的数据

---

此时,`kwages`变成了一个字典:
```python
kwages = {
'level': 'HIGH',
'message': "检测到rootkit注入",
}
```
此时,数据被打包成了一个叫做`kwages`的字典中,在内核中传输

---

内核找到了订阅者的`func`,
这个`func`就是`security_monitor`的`handle_alert`方法,
然后执行:
```python
func(**kwargs)
```
这里的双星号做了拆包的动作，把上面的那个字典拆开，还原成关键字参数
这行代码等价于：
```python
security_monitor.handle_alert(level="HIGH",message="检测到rootkit注入")
```

---

最终数据传输到目的地：
```python
# level 接收到 "HIGH"
# message 接收到 "..."
def handle_alert(self,level,message,**kwargs):
    print(f"\n>>>[警告] 级别: {level} | 内容: {message}")
```

---

