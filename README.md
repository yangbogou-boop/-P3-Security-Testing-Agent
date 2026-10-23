# P3 面向软件验收阶段的黑盒授权安全测试 Agent

当前 C-3C 候选新增离线 Supervisor、服务端摘要交付、独立证据关联、只读许可预检与 14 项验收管理清单；等待人工代码审核，未执行真实 HTTP。使用说明见 [生命周期设计](design/P3_supervisor_lifecycle.md)，交付与限制见 [C-3C 审核报告](review/P3_c3_supervisor_review.md)。以下历史阶段记录保留；真实集成始终为 PENDING_AUTHORIZATION，ADR-005 仍 Proposed。

> **课程名称**：专业综合能力提升
> **项目代号**：P3 - 黑盒授权安全测试 Agent（Planner–Controller 独立授权架构）  

## 项目定位与范围

面向软件测试人员和验收人员，用于集成测试与交付前验收。依据接口契约和预期权限矩阵，对 HTTP JSON API 执行黑盒未认证访问、对象级和角色级访问控制检查，不要求被测系统源码。

V1 仅面向经批准的本地隔离模拟 API，使用模拟身份和已批准只读请求，包含合法访问对照。所有请求先由不依赖 LLM 的 Controller 授权，再交由 Executor 派发。Controller 判断“可否发送测试请求”；权限矩阵及响应证据判断“API 是否正确允许或拒绝业务访问”。EXECUTED 不能代替 PASS，证据不足须为 INCONCLUSIVE，报告只对已检查范围给出有限结论。

## 文档与当前实现状态

[Specification V1.0-RC2](brief/P3_specification_v1.0-rc2.md)（当前候选；[RC1](brief/P3_specification_v1.0-rc1.md) 为原样历史快照） 是已获负责人文档审核的工程候选基线，正式课程契约及目录／预算门槛单独登记；[Problem Frame](brief/P3_problem_frame.md)、[授权边界](brief/P3_authorization_boundary.md)、[ADR 001](design/ADR_001_controller_split.md)、[ADR 002](design/ADR_002_black_box_api_scope.md) 记录定位、边界和历史取舍；[eval GWT](eval/P3_GWT_scenarios.md) 提供完整需求及场景定义；本轮仅执行离线控制子场景，状态见 [离线验证记录](eval/P3_offline_core_validation.md)。审批依据、A/B/C 决策与实验条件见 [治理登记](brief/P3_decision_governance.md)。

| 层次 | 状态 |
| --- | --- |
| 历史原型（保留） | `src/main.py`、`src/planner/`、`src/controller/` 的关键词扫描与模拟成功演示原样保留；不作为当前入口。 |
| 当前离线核心 | `src/p3_core/`：结构化模型、固定 Planner、独立 Controller、预算／撤权／终态、JSONL／Manifest／有限报告及 CLI；假派发不发送 HTTP。 |
| 无网络 HTTP 核心 | `src/p3_core/http/`：独立配置／许可快照、有限 GET 构造、有界解析／模拟判定、单 I/O 所有者状态机、内存传输及审计前缀分析。实际 HTTP 派发数仍为 0。 |
| 当前受控接入组件 | 已增加默认未激活的服务适配器、非阻塞 Executor、离线端到端框架、确定性策略比较及证据校验；实际网络路径尚未验收。 |
| V1 待验收 | 真实目标许可／教师目录核验、真实 HTTP 集成、实际取消／端口／代理边界、正式策略比较及课程 GWT 验收；全部实际网络项目 PENDING_AUTHORIZATION。 |
| 架构保证范围 | 当前为同进程模块分离，未实现物理隔离；不宣称能抵御任意同进程恶意代码。 |
| 已有证据 | 历史轨迹及公式模拟 Token 原样保留，不能证明真实 HTTP 测试、真实 LLM 成本或新版验收通过。 |
| 必做工程取舍 | 基础闭环后完成 REQ-021 固定／动态比较及 ADR 决定，依据课程任务映射为 MUST；可以保留固定 Baseline，不要求动态胜出或接入 LLM。 |
| 后续可选 | REQ-022 真实 LLM、GUI 及更强隔离；REQ-020 元数据仍为 MUST。 |

模拟 Bearer Token、GET／无请求体／无自动重试／不跟随重定向沿用负责人已确认的工程口径。8 项／90 秒／并发 1 是课程示例试跑值；课程 S3 第 40 张／稿034要求教师试跑后冻结本班预算，尚未有冻结记录。90 秒从静态预检后、首次规划前开始，初始规划计入预算；初始与追加共用累计 8 项额度，分别记录登记、尝试和实际请求数。终态不可通过追加重开，详见规格 §4。

固定／动态比较按 REQ-021 必做，采用相同声明目标、输入、授权、重置夹具与预算，报告课程七项指标及规划开销；6 项固定／3 项动态为示例，不强制照搬，不预设动态更优。课程资料核对后的第三轮修订已纠正旧 MAY；最终教学契约及任何正式豁免按 A-03／05 办理。

V1 不支持任意公网扫描、未经批准的写操作；图形界面和真实 LLM 不列为首版必需能力。负责人已确认 [ADR 003（Accepted：技术方案）](design/ADR_003_local_execution_and_evidence.md)，本轮只实现离线闭环；接入本地 HTTP 前仍须教师目录和目标所有者授权齐备，完成请求／响应契约、取消设计和后续验收。现有演示、离线测试与 CI 不替代真实请求验收。

## 👤 开发者信息
* 姓名：何镓欢
* **学号**：20241120224
* **专业班级**：网络空间安全

---

## 📁 目录结构与资产说明
* `brief/` - 项目契约、边界定义与威胁建模
* `design/` - 架构决策记录 (ADR)
* `eval/` - 待执行的 Given-When-Then 验收定义与需求映射（Markdown，不是自动化测试）
* `src/p3_core/` - 当前离线核心；其余 `src/` 旧演示源码保留
* `tests/` - 标准库 unittest 离线自动化测试
* `examples/offline.json` - 仅供离线控制验证的可信示例配置，不构成网络测试许可
* `evidence/` - 保留历史演示轨迹、模拟 Token 数据与工程证据
* `release/` - 规划目录：一键复现与环境部署说明，目前未建立
* `review/` - HTTP 设计审核及无网络核心审核报告；不作为真实 HTTP Evidence

2026-10-14：当前候选升级 RC2，历史 RC1 保留；教师事项只在对应执行／预算／验收／教学／评分阶段生效。NO_NEW_EVIDENCE 仅防无价值循环，不能因一次未发现漏洞跳过有价值的批准检查或必要对照；详见 RC2 与 GWT-A01-a～c。


## 离线运行与测试（Python 3.9+，仅标准库）

在仓库根目录的 PowerShell 执行：

```powershell
$env:PYTHONPATH = 'src'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m unittest discover -s tests -v
python -m p3_core --config examples/offline.json --output "$env:TEMP/p3-offline-runs"
```

Linux/macOS：`PYTHONPATH=src python -m unittest discover -s tests -v`；CLI 同样设置 `PYTHONPATH=src` 后运行。输出目录每次新建唯一 run 子目录，不覆盖历史 evidence。读取报告可用 `python -m json.tool <run目录>/report.json`，同时检查 Manifest 和 `audit_gap`。

CLI 退出码：0 表示离线计划正常处理完成，2 表示输入无效或运行停止，3 表示审计不完整。0 不代表 API 安全 PASS；本轮所有 API 结论为 INCONCLUSIVE，`request_count` 恒为 0。配置中的审批引用明确标记为离线夹具，不是实际目标授权。

测试使用假派发器、可控单调时钟和临时目录，并禁止创建网络套接字。CI 仅以只读仓库权限运行测试，不运行历史演示，不自动提交／推送 Evidence。旧演示中的模拟 EXECUTED 和公式 Token 仅属历史数据；不要用旧入口生成新版验收证据。

Controller 的 `start` 先静态预检再计时规划；`round(proposals=..., repeat=...)` 先处理检查及待决追加，再判定结束；可信宿主通过独立 `Revocation` 入口撤权，调用 `poll` 或下一调度检查点观察停止。Planner 无权获得该入口。具体映射、限制与真实测试结果见 [验证记录](eval/P3_offline_core_validation.md)。

## 第三阶段第二轮 B（2026-10-19）

[ADR-004](design/ADR_004_http_dispatch_and_cancellation.md) 已 Accepted，仅确认分离状态机＋单 I/O 所有者技术路线。新增模块没有网络后端、服务器或真实 HTTP CLI；原 offline CLI 与 49 项测试保持不变。完整 unittest 本地通过 103 项，新增 54 项均为无网络模拟，结果和限制见 [审核报告](review/P3_http_offline_core_review.md)。

测试命令沿用上文；只运行新增集可用 `python -m unittest discover -s tests -p test_http_core.py -v`（先设置 PYTHONPATH=src）。`SimulationRun.start/submit/step/settle/revoke/finalize` 提供模块级验证入口；使用方法和人工材料替身见 tests/test_http_core.py，不能把它当真实执行授权。step 只接受内存传输，一个 I/O 所有者逐步推进；settle 在待决追加后判断完成。

报告明确分列 `model_request_count` 与恒为 0 的 `request_count`，`simulated_conclusion` 与实际 `conclusion=INCONCLUSIVE`。所有执行仍为 NOT_EXECUTED，标注 NO_NETWORK_SIMULATION。没有真实 LLM、动态策略或 HTTP 集成结果；下一轮接入必须先完成目标许可／教师目录、真实传输边界与对应验收。

## 第三阶段第二轮 C-1：纯业务夹具（2026-10-19）

新增 `src/p3_core/mock_api/`：可信 FixtureManager 生成独立不可变实例和模拟凭据，Fixture.handle 接收结构化 GET 请求，返回规范化 MockResponse／HTTP 字节。实现 Good、Known Bad / AUTH、Known Bad / BOLA、Known Bad / RBAC 四种互斥模式；只使用既有个人资料、对象、管理员报表端点及合成数据。无 socket、服务器、登录／重置／模式管理 HTTP 入口。

完整 unittest 本地通过 **127 项（原 103＋新增 24）**；业务响应已与现有解析器、判定器及内存状态机兼容验证。新增单测可运行 `python -m unittest discover -s tests -p test_mock_api.py -v`，仍须设置 `PYTHONPATH=src`。真实 request_count 仍为 0，所有发现只属于无网络模拟。

接口、四模式结果、许可阻塞项及 C-2 待办见 [C-1 人工审核报告](review/P3_mock_api_c1_review.md)。服务监听、真实 Executor／响应证据、集成验收和 REQ-021 策略比较尚未完成；本轮不启动 C-2。


## 后续开发交付（2026-10-19，待人工代码审核）

本轮本地 158 项 unittest 通过（原 127 项保留，新增 31 项）。模拟 Good、AUTH、BOLA、RBAC 均完成配对判定，实际请求数始终为 0。36 次离线策略试跑未显示动态策略减少请求；推荐保留固定默认，见 [ADR-005（Proposed）](design/ADR_005_deterministic_strategy_comparison.md)。未启动服务，没有真实 HTTP 或 LLM 调用，未提交／推送。

新入口 `python -m p3_core.delivery` 提供 simulate、compare、validate、verify、network-plan；不提供真实网络启动开关。原 offline 入口保留。运行方法、可信宿主接口和许可门槛见 [交付说明](docs/P3_offline_delivery.md)。新增静态 live/service 模块只在可信宿主显式调用且登记核验通过后才可能创建 socket；本轮没有执行该路径。

完整交付见 [人工审核报告](review/P3_remaining_development_review.md)、[22 项需求追踪](eval/P3_requirement_traceability.md)、[逐次比较结果](eval/P3_offline_strategy_results.json) 和 [真实集成待验清单](eval/P3_http_integration_status.json)。前述 B、C-1 段落为历史基线记录，历史 Evidence 保留。
