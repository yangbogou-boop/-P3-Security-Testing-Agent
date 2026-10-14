# P3 第三阶段第一轮：离线核心验证记录

日期：2026-10-14。基线：[RC2](../brief/P3_specification_v1.0-rc2.md)。本记录描述离线自动化验证，不是 HTTP 安全测试报告、人工验收、教师审批或正式策略比较结果。

## 架构与入口

`可信配置 → 静态预检 → t0 → 固定 Planner → Controller → 假派发记录 → JSONL / Manifest / 有限报告`。

| 文件 | 职责 |
| --- | --- |
| `src/p3_core/models.py` | 严格字段验证、冻结授权／预算／端点／权限矩阵／候选模型，分开授权决定、执行状态与结论。 |
| `src/p3_core/planner.py` | 固定顺序确定性规划；同输入同输出，不裁剪超预算计划，不持有可写授权。 |
| `src/p3_core/controller.py` | 唯一离线派发入口、累计计数、可注入单调时钟、终态、追加／重复、防提前停止与有限报告。 |
| `src/p3_core/dispatch.py` | 非阻塞内存假派发器与独立可信撤权入口；无 HTTP、服务器或网络动作。 |
| `src/p3_core/evidence.py` | UUID 关联、脱敏 JSONL、独立 run 目录、独占创建 Manifest／报告和事件前缀校验。 |
| `src/p3_core/__main__.py` | 标准库 CLI，读取可信离线 JSON 配置，明确输入／运行／审计失败退出码。 |
| `src/p3_core/__init__.py` | 独立离线包声明。 |
| `examples/offline.json` | 仅离线夹具；对象负向提案和必要所有者对照，无原始凭据或实际许可声明。 |
| `tests/test_core.py` | unittest 测试；临时证据目录、内存派发、可控时间、故障注入与套接字禁止。 |
| `.github/workflows/ci_runner.yml` | 只读仓库权限运行测试；移除旧演示与自动 Commit／Push。 |

旧 `src/main.py`、`src/planner/agent_planner.py`、`src/controller/gateway.py` 未修改，历史证据未覆盖。旧模拟 EXECUTED／Token 不是新版证据。新包同进程模块分离，不提供任意恶意代码隔离。

`plan_count` 为累计登记，`attempt_count` 为接纳首次校验，`request_count` 仅计实际 HTTP；本轮恒为 0。另记 `offline_dispatch_count` 观察允许的假派发，不能用其冒充真实请求数。无实际响应的检查不写 EXECUTED、PASS 或 FAIL。

## 需求与已实现范围

| 实现 | RC2 需求 ID | 本轮验证边界 |
| --- | --- | --- |
| 结构化配置、端点、矩阵、候选和对照引用预检 | P3-REQ-001、002、008 | 离线输入及只读／回环约束；完整响应契约与实际目标授权仍待接入。 |
| 固定 Planner、可信配置快照、不可变候选 | P3-REQ-003、007、009 | 固定确定性成立；非 LLM 独立判断，不执行响应中的指令。 |
| 精确端点／方法／身份／参数组合及候选校验 | P3-REQ-007、008、009 | 非法提案拒绝，不回收已用名额或尝试。 |
| 三计数、8 项边界、90 秒、串行和终态 | P3-REQ-010、012、015 | 试跑参数可配置；时间起点在首次规划前；假派发不计 HTTP。 |
| 可信撤权及授权有效期检查 | P3-REQ-009、011、012 | 新假派发停止；真实网络在途取消尚未实现。 |
| 无新增证据防循环及防提前停止 | P3-REQ-010、014、017 | 核对所有批准候选及必要对照；无真实响应或漏洞判定。 |
| 独立结果模型与有限报告 | P3-REQ-014、017 | 所有 API 结论 INCONCLUSIVE；列出未完成、未覆盖、拒绝和证据限制。 |
| UUID、允许／拒绝／停止审计、脱敏和 Manifest | P3-REQ-015、016、012 | 历史不覆盖、无原始模拟凭据；运行中审计失败安全停止。 |
| 配置／CLI 与版本、候选、预算、规划耗时元数据 | P3-REQ-019、020 | 可复现离线入口；没有伪造 HTTP 成本、LLM Token 或实验比较。 |

这些是需求的离线子集，不将表中映射等同于全部 V1 MUST 已满足。

## 自动化测试及实际结果

在仓库根目录执行：

```powershell
$env:PYTHONPATH = 'src'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m unittest discover -s tests -v
```

本地环境：Windows、Python 3.9.12；使用标准库，无新第三方依赖。已在当前仓库实际运行：42 项测试全部通过，耗时 0.392 秒，退出码 0。另运行随附 examples/offline.json：run_8af06a75ebf84a97ba114d2aac19cc25，COMPLETED，plan_count=3、attempt_count=3、request_count=0、offline_dispatch_count=3；3 项均 NOT_EXECUTED / INCONCLUSIVE，审计无缺口。测试证据使用临时目录；示例产物保存在本次会话 outputs/p3-core-review/runs 下，未写入仓库历史 Evidence。CI 配置为 Python 3.10，尚未在 GitHub 实际运行，不宣称 CI 已通过。

覆盖包括合法／畸形初始计划、未注册端点／身份／参数／写方法、缺失或矛盾矩阵、拒绝不回收预算、6+2 累计、第 8 项与第 9 项、重复和替换拒绝、终态不重开、首次规划耗时、89／90 秒、审计处理耗时、墙钟回拨、单调钟倒退、撤权及多原因优先、假派发异常／超时、审计故障、唯一 ID、脱敏、线程串行、重入拒绝和 CLI 退出码。

GWT-A01-a/b/c 分别由 `test_gwt_a01_a_repeat_stops_only_exhausted_valuable_work`、`test_gwt_a01_b_no_findings_does_not_skip_remaining_check`、`test_gwt_a01_c_control_is_not_skipped_even_when_not_initially_planned` 验证离线控制行为。b/c 没有伪造 HTTP 403／404 或“未发现漏洞”业务结论：测试使用无响应假派发验证不能提前停止，HTTP 版本仍待验证。

N04-a 的离线变体观察 8 次尝试、7 次假派发、0 次真实请求；不能把规格 HTTP 场景中的 request_count=7 写成已达成。N05 的“在途”测试也仅是注入回调耗时，不证明网络超时或取消实现。

## 尚未实现与对应 GWT

| 剩余工作 | RC2 / GWT |
| --- | --- |
| 本地 HTTP Executor、端点路由、禁止代理／重定向、凭据解析、真实请求和响应留证 | REQ-002、007、013；GWT-P01、A02、N06 |
| 正确／已知缺陷 API 夹具、三类权限断言、对照成立与泄露／过度拒绝判定 | REQ-001、004～006、014、018；GWT-P02、N02、N07 |
| 真实请求剩余超时、撤权竞态／在途取消及迟到响应 | REQ-010～012；GWT-N05-b、A03、A03-a |
| 真实响应脱敏、截断、容量与完整性试跑 | REQ-015、016；GWT-P03、N07；C-03 |
| HTTP 版本完整闭环复现、覆盖／成本实测 | REQ-017～020；GWT-P04、N04、N07 |
| 固定／动态策略比较和实验后的 ADR 取舍 | REQ-021 MUST；GWT-P05、P05-a/b；C-02 |
| 真实 LLM | REQ-022 MAY；GWT-A04；不在本轮范围。 |

运行中审计失败进入 STOPPED/AUDIT_ERROR；若失败与撤权等同时被观察，遵循 RC2 优先级。已冻结终态后的文件收尾失败不重开或改写终态，而以 `audit_gap`、`audit_error` 和 CLI 退出码 3 告知证据不足。Manifest 缺失／损坏不视为完整运行证据。单机追加文件及校验不是防篡改、签名或断电持久性保证。

## 下一轮接入本地模拟 API 前

1. 本轮代码与离线验证先经人工审核；明确批准下一轮范围。
2. A-01 教师目标／测试目录及目标所有者／授权负责人许可齐备，登记具体端点、身份、动作、有效期与预算。离线示例中的批准者和许可引用不能复用作真实授权。
3. 完善可信接口契约、权限矩阵、响应断言、模拟身份／对象及 Good／Known Bad 夹具，确认必要合法访问对照。
4. 设计真实 Executor 的强制入口、无代理／重定向／重试、剩余超时、可取消派发及撤权交界；同步假派发锁不得直接包住阻塞 HTTP。
5. 明确响应敏感字段、截断及证据缺口规则，再实施 C-01／C-03 试跑。8／90／1 未教师冻结，不宣称数字已合理。
6. 基础 HTTP 闭环之后实施 REQ-021 的公平策略比较；正式教学验收／评分仍按 A 类阶段办理。

本轮没有自动 Commit、Push 或开始 HTTP Executor 开发。


## 2026-10-14 源码审核后的定点修复

保留上述首轮 42 项测试记录。本轮仅修复 Controller 的两个审核问题，未改变 RC2 §4、稳定需求 ID、ADR-003 技术路线或网络能力。

- 重复 ID 冲突原先调用 `_attempt(existing, ...)`，错误消耗原检查的首次尝试并标记为已处理。现在只记录 `conflicting_proposal_rejected` 与原因、提案 ID、原 slot 关联，不改变原检查任何状态或计数；原合法检查仍按原计划处理。累计第 8／9 项及新畸形提案预算规则不变。
- 原先把语法解析成功当成可完整留证，且通用 Redactor 无法识别未登记的任意敏感参数。现在在 Controller 输出边界只序列化与可信候选完全一致的检查；其他提案只保留生成的 proposal_id、可信关联、内容省略标志及固定原因／统计，不保存原始参数、未知 ID、异常正文或原始提案摘要哈希。事件、待执行报告、拒绝报告与最终产物使用同一筛选规则。证据层仍执行既有已知敏感值脱敏，未扩大为通用内容识别器。
- 每个已登记 slot 关联生成的 proposal_id，登记事件、授权决定与报告可相互关联；批准检查保留正常字段与 evidence_id 关联。冲突提案使用独立 proposal_id，不覆盖原检查。

先添加回归测试，在旧代码上确认失败，再应用修复。当前仓库执行 `PYTHONPATH=src python -m unittest discover -s tests -v`（PowerShell 环境设置按上文）：Python 3.9.12，49 项全部通过，耗时 0.703 秒，退出码 0。修改原有 `test_registered_plan_cannot_be_replaced_before_attempt` 的错误预期，新增 7 项回归测试：

| 测试 | 结果与覆盖 |
| --- | --- |
| `test_malformed_duplicate_preserves_all_original_check_state` | 通过：缺字段、错误参数类型及未知字段冲突均保留原检查，之后正常处理。 |
| `test_conflict_at_full_budget_preserves_eighth_and_ninth_rules` | 通过：满额度时冲突不消耗原检查，真正第 9 项仍预算停止。 |
| `test_conflicts_do_not_consume_new_malformed_proposal_budget` | 通过：冲突不计首次尝试，新畸形提案仍分别占累计名额／尝试。 |
| `test_unapproved_payloads_absent_from_all_evidence_and_reports` | 通过：7 条提交路径；未向 secrets 列表登记人工敏感字符串，扫描全部生成文件、内存报告和证据层输入，无原始字符串。 |
| `test_rejected_proposal_ids_correlate_without_raw_check` | 通过：拒绝项不保留原始检查，proposal／slot／attempt 与原因可关联。 |
| `test_approved_check_evidence_association_is_preserved` | 通过：可信批准检查的字段和证据关联不丢失。 |
| `test_exception_body_absent_from_files_and_report` | 通过：人工异常敏感正文不进入生成文件或报告。 |

测试仍禁止网络套接字，使用临时目录；历史 Evidence 未修改。最小摘要有意放弃未批准原始载荷的完整重放，内部受控检查对象仍用于校验，不能把调试对象转储当成安全证据接口。可信配置必须由可信入口维护，已批准数据中的已知模拟凭据沿用显式脱敏；本轮不证明未来 HTTP 响应的脱敏／截断已完成。未 Commit 或 Push，等待人工审核。
