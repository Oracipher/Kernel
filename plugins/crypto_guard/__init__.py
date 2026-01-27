# plugins/crypto_guard/__init__.py

from interface import Proot
from .engine import CryptoEngine

class Plugin(Proot):
    def start(self):
        self.api.log("初始化安全协处理器 (Crypto Co-processor)...")
        
        # 实例化核心引擎
        self.engine = CryptoEngine()
        
        # --- 注册系统级服务 ---
        # 监听其他插件发出的 'req:sign' 请求
        self.api.on("req:sign", self._handle_sign_request)
        # 监听 'req:verify' 请求
        self.api.on("req:verify", self._handle_verify_request)
        
        # 在系统配置中标记本服务已在线
        self.api.set_data("service.crypto", "ONLINE")
        self.api.log("服务已就绪: [req:sign], [req:verify]")

    def stop(self):
        self.api.set_data("service.crypto", "OFFLINE")
        del self.engine
        self.api.log("安全协处理器已卸载，密钥已销毁。")

    # --- 事件回调处理 ---

    def _handle_sign_request(self, payload, request_id):
        """
        处理签名请求
        payload: 需要签名的数据
        request_id: 请求者的ID（用于写回结果）
        """
        self.api.log(f"正在为请求 {request_id} 执行签名...")
        
        sig, success = self.engine.sign_data(payload)
        
        if success:
            # 将结果写入公共数据交换区（模拟硬件寄存器）
            # Key 格式: buffer:crypto:{request_id}
            result_key = f"buffer:crypto:{request_id}"
            
            result_data = {
                "status": "OK",
                "payload": payload,
                "signature": sig
            }
            self.api.set_data(result_key, result_data)
            
            # 发送完成信号
            self.api.impulse(f"res:sign:{request_id}", result=result_data)
        else:
            self.api.log(f"签名失败: {sig}")

    def _handle_verify_request(self, payload, signature, request_id):
        """处理验签请求"""
        is_valid = self.engine.verify_data(payload, signature)
        
        result_key = f"buffer:crypto:{request_id}"
        self.api.set_data(result_key, {"valid": is_valid})
        self.api.impulse(f"res:verify:{request_id}", valid=is_valid)