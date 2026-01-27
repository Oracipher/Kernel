
# plugins/audit_tester.py

from interface import Proot

class Plugin(Proot):
    def start(self):
        self.api.log("测试者上线...")
        
        # 1. 模拟写入
        self.api.impulse("audit:record", event_type="LOGIN", message="Admin login attempt")
        
        # 2. 注册查询结果的回调监听
        # 这里的事件名必须唯一，防止与其他插件冲突
        my_callback_event = "audit:result:tester"
        self.api.on(my_callback_event, self.handle_query_result)
        
        # 3. 发起查询，并告知对方把结果发到哪里 (Callback Pattern)
        self.api.log("正在请求审计记录...")
        self.api.impulse("audit:query", limit=2, callback_event=my_callback_event)

    def stop(self):
        pass

    def handle_query_result(self, data):
        """处理异步返回的查询结果"""
        self.api.log(f"收到查询结果，共 {len(data)} 条记录：")
        for row in data:
            # row 结构: (id, ts, type, msg, hash)
            self.api.log(f" >> [{row[1]}] {row[3]}")