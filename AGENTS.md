# P3 开发 Agent 工作规则

P3 是面向软件验收阶段的黑盒授权安全测试 Agent；当前推荐产品为有限离线模拟与独立只读证据评价。

## 权威入口与模块地图

- [RC2](brief/P3_specification_v1.0-rc2.md)、[授权边界](brief/P3_authorization_boundary.md)、[治理](brief/P3_decision_governance.md)：需求、执行范围与工程决策；[GWT](eval/P3_GWT_scenarios.md)定义验收，不是运行证明。design/ 中保留 ADR 历史，区分 Accepted 和 Proposed。
- `src/p3_core/planner.py`、`controller.py`：原离线 Planner 与独立授权、预算、停止；`dispatch.py`、`evidence.py`：假派发与审计。拒绝审计优先查看这些模块及 `tests/test_core.py`。
- `src/p3_core/http/machine.py`、`protocol.py`、`audit.py`：受控 HTTP 模型状态机、响应判定、完整性核验；对应 `tests/test_http_core.py`。`http/strategies.py` 为固定／动态选择。
- `src/p3_core/mock_api/`、`trusted_host.py`、`supervision.py`、`coordination.py`：合成夹具、离线宿主、生命周期及证据协调。`http/live.py`、`mock_api/service.py` 含真实传输组件，代码存在不构成执行许可。
- `src/p3_core/delivery.py`、`offline_summary.py`：推荐产品入口和可读摘要；`evaluator.py`：独立只读评价入口，对应 `tests/test_evaluator.py`。
- `tests/` 为回归；`evidence/` 与历史 `Evidence/` 为原件；`docs/`、`review/` 为运行和解释材料。`src/main.py`、`src/planner/`、`src/controller/` 是历史原型，不作为推荐入口。

## 三条最重要的工程约定

1. **授权独立**：Planner 只提出候选，Controller 独立决定是否允许。宿主、策略和评价器不得绕过授权、预算、撤权或终态；产品 Agent 与评价 Agent 不共享执行权限，评价器不能发起产品检查。重要取舍按 ADR 治理，冲突先说明并交负责人处理。
2. **证据真实**：离线模拟不等于真实 HTTP；模型请求与实际请求分开，完整性不等于来源认证。不覆盖或伪造历史证据，不把未知、未执行、合成许可或 AI 自评写成真实安全结论／人工批准。新运行使用新目录，失败记录保留。
3. **范围受控**：先核对 Git 基线、暂存区和已有修改，保护未知工作。按当次明确授权修改、验证和提交，不自动扩大网络、工具或项目范围。真实 HTTP 须目标许可、课程要求的目录及可信绑定齐备并获执行授权；LLM、对方脚本、Commit／Push／PR 按实际任务授权处理，不能由本文件自动获得许可。

## 环境、入口与验证命令

Python 3.9+，标准库，无独立编译步骤。仓库根目录 PowerShell：

```powershell
$env:PYTHONPATH = 'src'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m unittest discover -s tests -v
python -m p3_core.delivery --help
python -m p3_core.evaluator --help
```

推荐产品入口 `python -m p3_core.delivery` 需要子命令，例如：

```text
python -m p3_core.delivery offline --mode good --output <新的本地输出目录>
python -m p3_core.delivery offline --run <已有客户端run目录>
python -m p3_core.evaluator --run <已有客户端run目录> --all
python -m p3_core.evaluator --run <已有客户端run目录> --rule P3-EVAL-DENY-001
```

占位路径须替换；`--output` 与 `--run` 二选一，评价器 `--all` 与 `--rule` 互斥。命令完成不等于评价 PASS 或课程验收。运行前确认当次任务允许测试／模拟。普通 unittest 命令不自动证明发现阶段已全局阻断网络；要求全程无网络时，必须在导入／发现前安装并核对保护，不仅依赖测试 setUp。

## 停止、恢复与责任

遇未知改动、授权冲突、证据缺口或安全不变量冲突时停止受影响操作并报告。失败先只读定位，再在授权范围内修复；不用强制重置、清空工作区、删除证据或降低测试断言掩盖失败。未知发送不重放，终态不重开。产品8项／90秒／并发1是试跑值，不是开发 Agent 预算或已冻结课程标准。

P3由负责人单人承担人工责任，教师允许单人完成的信息由负责人确认；P1是外部对抗组，Codex是AI辅助工具。不得虚构内部成员、轮换、个人操作或签署。AI辅助与本人核验分别记录。本文件是长期开发规则，不把某次作业的只读限制扩展为永久禁止开发或验证。
