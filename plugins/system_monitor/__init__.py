import time
import random
from interface import IPlugin

class Plugin(IPlugin):
    """
    经典示范插件：系统监控器
    展示特性：依赖管理、后台线程托管、事件同步/异步调用、全局数据共享
    """

    def start(self) -> None:
        self.api.log(">>> 系统监控器正在初始化...")

        # 1. [特性: 配置读取] 读取 config.json 中的 settings 字段
        config = self.api.get_plugin_config()
        self.settings = config.get("settings", {"tick_interval": 3.0})
        self.interval = self.settings.get("tick_interval", 3.0)

        # 2. [特性: 依赖检查与数据获取] 
        # 因为我们在 config.json 声明了依赖 core_system，所以此时它一定已经启动了
        # 我们可以安全地读取它的数据
        core_status = self.api.get_data("core_status", scope="global")
        self.api.log(f"依赖检查: Core System 状态为 [{core_status}]")

        # 3. [特性: 事件监听] 注册一个同步事件，供外部查询详情
        # 当有人调用 api.call("monitor_report") 时，会执行此函数
        self.api.on("monitor_report", self._handle_report_request)

        # 4. [特性: 资源托管] 启动后台线程
        # 注意：不要自己 threading.Thread(...).start()，要交给 API 托管
        self.api.spawn_task(self._background_worker, daemon=True)
        
        self.api.log(f"启动完成 (采样间隔: {self.interval}s)")

    def stop(self) -> None:
        """
        [特性: 生命周期管理]
        内核调用 stop 后，api.is_active 会变为 False。
        后台线程检测到后会自动退出，无需在此手动 kill 线程。
        """
        self.api.log("<<< 系统监控器正在停止，保存最终状态...")
        # 可以在这里做最后的清理或数据持久化

    def _background_worker(self):
        """
        [重点教学] 后台任务的标准写法
        """
        self.api.log("后台监控线程已启动")
        
        while True:
            # === [关键点] ===
            # 必须在循环中检查 API 活性，否则卸载插件时会产生僵尸线程
            if not self.api.is_active:
                self.api.log("检测到停止信号，后台线程退出")
                break
            # ===============

            # 模拟业务逻辑：生成监控数据
            stats = {
                "cpu_mock": random.randint(10, 90),
                "memory_mock": random.randint(200, 1024),
                "timestamp": time.time()
            }

            # 5. [特性: 数据共享] 更新本地数据，允许其他插件通过 get_data 读取
            self.api.set_data("realtime_stats", stats, scope="local")

            # 6. [特性: 异步事件分发] 广播心跳包
            # Fire-and-forget，不等待结果
            self.api.emit("system_heartbeat", source="system_monitor", data=stats)
            
            # 使用简单的 sleep 模拟耗时
            # 在高精度场景下，建议使用带超时的 event.wait() 以便更敏捷地响应停止信号
            time.sleep(self.interval)

    def _handle_report_request(self, **kwargs):
        """
        [特性: 同步事件回调]
        被 api.call("monitor_report") 调用。会阻塞调用者直到返回。
        """
        requester = kwargs.get("requester", "unknown")
        self.api.log(f"收到来自 {requester} 的报表请求")
        
        # 从共享数据区拿最新数据
        current_data = self.api.get_data("realtime_stats", scope="local")
        
        return {
            "status": "OK",
            "plugin": "system_monitor",
            "data": current_data,
            "message": "一切正常，指挥官"
        }