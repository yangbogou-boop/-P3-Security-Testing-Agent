# src/controller/gateway.py
import json
import os
import time

class SecurityController:
    """
    独立控制器 (Controller - 内核态网关)
    完全由硬编码和强类型数据结构实现，不依赖 AI。
    职责：对 Planner 提交的意图进行 100% 的白名单静态校验。
    """
    def __init__(self):
        # 不可变的授权白名单矩阵
        self.allowed_targets = {"192.168.1.10"}
        self.allowed_tools = {"nmap_lite", "dir_buster"}

    def validate_and_execute(self, intent_json: str) -> dict:
        """
        拦截并校验 Planner 的意图
        """
        try:
            intent = json.loads(intent_json)
        except json.JSONDecodeError:
            return {"status": "BLOCKED", "reason": "Invalid JSON format from Planner."}

        target = intent.get("target")
        tool = intent.get("tool")
        action = intent.get("action")

        # 核心硬干预校验逻辑
        if target not in self.allowed_targets or tool not in self.allowed_tools:
            # 越权或非法工具尝试，直接阻断
            return {
                "status": "BLOCKED",
                "reason": f"PermissionDenied: Target '{target}' or Tool '{tool}' is not in the whitelist."
            }

        # 校验通过，模拟路由至物理执行器
        run_id = f"RUN_{int(time.time())}"
        result = {
            "run_id": run_id,
            "status": "EXECUTED",
            "message": f"Successfully executed action '{action}' on target '{target}' using tool '{tool}'."
        }
        
        # 自动留存运行证据 Trace 到本地（模拟器环境）
        self._save_trace(run_id, intent, result)
        return result

    def _save_trace(self, run_id: str, intent: dict, result: dict):
        """
        自动落盘证据与 Token/轨迹日志
        """
        os.makedirs("evidence/traces", exist_ok=True)
        trace_data = {
            "run_id": run_id,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "intent": intent,
            "result": result
        }
        with open(f"evidence/traces/{run_id}.json", "w", encoding="utf-8") as f:
            json.dump(trace_data, f, indent=2, ensure_ascii=False)
