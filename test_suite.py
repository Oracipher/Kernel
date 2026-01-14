import unittest
import os
import shutil
import time
import json
import threading
import sys
# import concurrent.futures
# from typing import Dict, List, Any

# 导入你的项目模块
from kernel import PluginKernel
# from interface import IPlugin

# ----------------------------------------------------------------
# 测试辅助工具
# ----------------------------------------------------------------

TEST_PLUGIN_DIR = "test_plugins_env"

class MicroKernelTestSuite(unittest.TestCase):
    """
    微内核架构全方位测试套件
    """

    def setUp(self):
        """每个测试用例运行前的准备工作"""
        # 1. 创建干净的测试目录
        if os.path.exists(TEST_PLUGIN_DIR):
            shutil.rmtree(TEST_PLUGIN_DIR)
        os.makedirs(TEST_PLUGIN_DIR)
        
        # 2. 初始化内核
        # 为了测试方便，我们需要 Monkey-Patch 内核的插件目录指向测试目录
        self.kernel = PluginKernel()
        self.kernel.PLUGIN_DIR = TEST_PLUGIN_DIR
        
        # 清理之前的模块缓存，防止测试干扰
        for k in list(sys.modules.keys()):
            if k.startswith("mk_plugin_"):
                del sys.modules[k]

    def tearDown(self):
        """每个测试用例结束后的清理工作"""
        self.kernel.shutdown()
        # 强制清理临时目录
        if os.path.exists(TEST_PLUGIN_DIR):
            try:
                shutil.rmtree(TEST_PLUGIN_DIR)
            except PermissionError:
                # Windows下有时候文件会被短暂占用，忽略即可
                pass

    def _create_plugin(self, name: str, version: str = "1.0.0", deps: list = None, 
                    code: str = None, config_extras: dict = None):
        """辅助函数：快速生成一个插件文件结构"""
        if deps is None:
            deps = []
        
        p_dir = os.path.join(TEST_PLUGIN_DIR, name)
        os.makedirs(p_dir)
        
        # 生成 config.json
        cfg = {
            "name": name,
            "version": version,
            "dependencies": deps
        }
        if config_extras:
            cfg.update(config_extras)
            
        with open(os.path.join(p_dir, "config.json"), "w", encoding='utf-8') as f:
            json.dump(cfg, f)
            
        # 生成 __init__.py
        default_code = """
from interface import IPlugin
class Plugin(IPlugin):
    def start(self):
        self.api.log(f"{self._plugin_name} started")
    def stop(self):
        self.api.log(f"{self._plugin_name} stopped")
        """
        with open(os.path.join(p_dir, "__init__.py"), "w", encoding='utf-8') as f:
            f.write(code if code else default_code)

    # ----------------------------------------------------------------
    # 第一部分：依赖管理与加载逻辑测试
    # ----------------------------------------------------------------

    def test_01_dependency_order(self):
        """测试：依赖拓扑排序是否正确"""
        print("\n--- Test 01: Dependency Topology ---")
        # 创建链式依赖: C 依赖 B, B 依赖 A
        self._create_plugin("plugin_A")
        self._create_plugin("plugin_B", deps=["plugin_A"])
        self._create_plugin("plugin_C", deps=["plugin_B"])
        
        self.kernel._scan_plugins()
        order = self.kernel._resolve_dependencies()
        
        print(f"Calculated Order: {order}")
        self.assertEqual(order, ["plugin_A", "plugin_B", "plugin_C"])

    def test_02_circular_dependency(self):
            """测试：循环依赖是否导致插件被忽略"""
            print("\n--- Test 02: Circular Dependency ---")
            # A 依赖 B, B 依赖 A
            self._create_plugin("plugin_A", deps=["plugin_B"])
            self._create_plugin("plugin_B", deps=["plugin_A"])
            
            self.kernel._scan_plugins()
            
            # 内核会捕获异常并打印日志，而不是抛出异常
            # 所以我们不应该用 try...except 捕获，而是检查结果
            load_order = self.kernel._resolve_dependencies()
            
            print(f"Load Order (Should be empty): {load_order}")
            
            # 验证：因为循环依赖，内核应该放弃加载这两个插件
            self.assertNotIn("plugin_A", load_order, "plugin_A should be ignored due to circular dep")
            self.assertNotIn("plugin_B", load_order, "plugin_B should be ignored due to circular dep")

    def test_03_version_mismatch(self):
            """测试：版本号不匹配是否导致插件被忽略"""
            print("\n--- Test 03: Version Mismatch ---")
            self._create_plugin("lib_base", version="1.0.0")
            self._create_plugin("app_tool", deps=["lib_base>=2.0.0"]) # 需要 2.0.0
            
            self.kernel._scan_plugins()
            
            # 同样，内核不会崩溃，只会忽略不满足条件的插件
            load_order = self.kernel._resolve_dependencies()
            
            print(f"Load Order: {load_order}")
            
            # 验证：lib_base 应该存在，但 app_tool 应该被剔除
            self.assertIn("lib_base", load_order)
            self.assertNotIn("app_tool", load_order, "app_tool should be ignored due to version mismatch")
    # ----------------------------------------------------------------
    # 第二部分：安全性与隔离测试
    # ----------------------------------------------------------------

    def test_04_security_audit_banned_imports(self):
        """测试：是否拦截 import os"""
        print("\n--- Test 04: Security Audit (Imports) ---")
        malicious_code = """
from interface import IPlugin
import os  # <--- Banned
class Plugin(IPlugin):
    def start(self):
        os.system('echo hacked')
    def stop(self): pass
        """
        self._create_plugin("hacker_plugin", code=malicious_code)
        
        self.kernel._scan_plugins()
        success = self.kernel.load_plugin("hacker_plugin")
        
        self.assertFalse(success, "Kernel should refuse to load plugin with 'import os'")

    def test_05_security_audit_banned_calls(self):
        """测试：是否拦截 eval() 调用"""
        print("\n--- Test 05: Security Audit (Eval) ---")
        malicious_code = """
from interface import IPlugin
class Plugin(IPlugin):
    def start(self):
        eval("print('hacked')") # <--- Banned
    def stop(self): pass
        """
        self._create_plugin("eval_plugin", code=malicious_code)
        
        self.kernel._scan_plugins()
        success = self.kernel.load_plugin("eval_plugin")
        
        self.assertFalse(success, "Kernel should refuse to load plugin with 'eval()'")

    # ----------------------------------------------------------------
    # 第三部分：并发与稳定性测试 (Stress Test)
    # ----------------------------------------------------------------

    def test_06_start_timeout(self):
        """测试：插件启动超时是否熔断"""
        print("\n--- Test 06: Start Timeout ---")
        # 模拟一个启动需要 5秒 的插件，内核限制是 3秒
        slow_code = """
from interface import IPlugin
import time
class Plugin(IPlugin):
    def start(self):
        time.sleep(5) 
    def stop(self): pass
        """
        self._create_plugin("slow_plugin", code=slow_code)
        
        self.kernel._scan_plugins()
        start_time = time.time()
        success = self.kernel.load_plugin("slow_plugin")
        end_time = time.time()
        
        print(f"Load attempted in {end_time - start_time:.2f}s")
        self.assertFalse(success, "Should fail due to timeout")
        self.assertTrue(end_time - start_time < 4.0, "Kernel waited too long")

    def test_07_concurrency_data_race(self):
        """测试：多线程疯狂读写 Context 是否引发崩溃"""
        print("\n--- Test 07: Concurrency Stress Test ---")
        
        # 预先填充数据
        self.kernel.context_global["counter"] = 0
        
        def worker_task():
            # 模拟高频读取和写入
            for _ in range(100):
                # 写入：利用 kernel 锁保护
                with self.kernel._lock:
                    val = self.kernel.context_global["counter"]
                    self.kernel.context_global["counter"] = val + 1
                # 读取
                self.kernel.thread_safe_get_data("tester", "counter", "global", 0)

        # 启动 20 个线程并发冲击
        threads = [threading.Thread(target=worker_task) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        final_val = self.kernel.context_global["counter"]
        print(f"Final Counter: {final_val} (Expected: 2000)")
        self.assertEqual(final_val, 2000, "Race condition detected! Counter lost updates.")

    # ----------------------------------------------------------------
    # 第四部分：事件系统测试
    # ----------------------------------------------------------------

    def test_08_sync_event_call(self):
        """测试：同步事件调用与返回值"""
        print("\n--- Test 08: Sync Event Call ---")
        
        code_responder = """
from interface import IPlugin
class Plugin(IPlugin):
    def start(self):
        self.api.on("ping", self.pong)
    def stop(self): pass
    def pong(self, **kwargs):
        return f"pong from {kwargs.get('src')}"
        """
        self._create_plugin("responder", code=code_responder)
        
        self.kernel._scan_plugins()
        self.kernel.load_plugin("responder")
        
        # 内核发起同步调用
        results = self.kernel.sync_call_event("ping", src="test_unit")
        
        print(f"Event Results: {results}")
        self.assertEqual(results[0], "pong from test_unit")

    def test_09_resource_cleanup(self):
        """测试：插件卸载后，Managed Thread 是否被标记停止"""
        print("\n--- Test 09: Resource Cleanup & Zombie Threads ---")
        
        code_thread = """
from interface import IPlugin
import time
import threading

class Plugin(IPlugin):
    def start(self):
        self.api.spawn_task(self.worker)
    def stop(self): 
        self.api.log("Stopping...")
        
    def worker(self):
        while self.api.is_active:
            time.sleep(0.1)
        # 写入一个文件证明自己退出了
        with open('thread_exit_signal', 'w') as f:
            f.write('EXITED')
        """
        self._create_plugin("threaded_plugin", code=code_thread)
        
        # 1. 加载
        self.kernel._scan_plugins()
        self.kernel.load_plugin("threaded_plugin")
        
        # 确认线程在运行
        api = self.kernel.plugins_meta["threaded_plugin"].api_instance
        self.assertEqual(len(api._managed_threads), 1)
        
        # 2. 卸载
        self.kernel.unload_plugin("threaded_plugin")
        
        # 3. 验证线程是否退出
        # 给一点点时间让线程写文件
        time.sleep(0.5) 
        self.assertTrue(os.path.exists("thread_exit_signal"), "Background thread did not exit correctly!")
        
        # 清理
        if os.path.exists("thread_exit_signal"):
            os.remove("thread_exit_signal")

if __name__ == '__main__':
    unittest.main()