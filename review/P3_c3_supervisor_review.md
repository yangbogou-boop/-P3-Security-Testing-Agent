# 当前交付状态（2026-10-22）

最新候选为 **258 项测试通过、12 种重置竞争时序通过**。本文按修订顺序保留历史章节；所有 217、227、237、257 项及对应“当前”“本次”表述均为该历史轮次记录，不是最新总数。最新修复说明见末尾“最终定点修复”。真实 HTTP 验收仍为 PENDING_AUTHORIZATION。

# C-3C 可信监督者与双端证据协调审核报告

日期：2026-10-21。实际仓库：`D:\project\-P3-Security-Testing-Agent`。基线 HEAD：`3199b3f9a447cc15548523c995548f139cf8bc18`。本轮仅离线开发，等待人工代码审核；未 Commit／Push，未执行实际 HTTP、DNS、socket 或服务监听。本报告不是正式课程或真实网络验收报告。

## 最新修订：重置提交点竞态

本次在 227 项基线上新增 10 项确定性测试，全量 **237 项通过**。工作区累计 16 个变更文件，新增修改的原有文件是 `src/p3_core/mock_api/core.py`；此前全部工作保留。以下 15 文件、217／227 项等文字保留为此前阶段记录，以本节为当前结果。

原问题：prepare_next 提前预约 RETIRED，然后在端点复核后无条件调用 reset；失败通知即使已锁存，也只能在创建之后抛异常。修复前新增测试明确出现实际 Fixture 构造 1 次而预期 0 次；52 项 Supervisor 测试为 3 failures／4 errors（部分新测试等待新状态字段和准备接口）。独立审核的 `independent-review-race.json` 同样记录旧实现 reset 调用 1 次。

修复：确认 FixtureManager 无全局活动实例后，提取锁外的纯候选工厂 prepare，保留原 reset 兼容接口。Supervisor 将准备资格与正式提交分离；提交和可信失败通知共享短状态锁，以递增序号给出唯一先后顺序。提交边界只有内存引用与元数据赋值。所有构造、文件校验、外部审计和旧绑定失效都在锁外。

失败先赢时正式提交数为 0；候选若已在锁外生成，明确计作一次私有构造而非一次激活，不作废旧绑定。提交先赢时记录提交事实，后续失败进入 FAILED、撤下候选且禁止重试，不能清除 audit_failed 或声称已提交对象不存在。报告和可用审计事件记录 commit／failure 序号。完整先后顺序表见 [生命周期设计](../design/P3_supervisor_lifecycle.md)。

10 项新增回归覆盖：端点复核屏障失败（实际构造 0／提交 0）、候选准备后失败（1／0）、提交先赢后失败（1／1）、双线程最多一次构造／提交、准备审计失败（1／0）、端点检查异常（0／0）、旧 generation／错实例／重复失败、锁外操作验证、提交后审计写入失败（1／1）、错误准备实例拒绝且不可重试。原 227 项测试与断言保持。

修复后按原独立审核步骤再次使用真实 JsonlEvidence 临时目录、篡改 Manifest.audit_gap、端点 Event 屏障复现：completion=AUDIT_FAILED，实际 Fixture 构造 0 次，兼容 reset 调用 0 次，正式提交 0 次，旧绑定未失效，旧 generation=1，最终 FAILED。结果保存在 `reset-commit-race-after.json`。

当前全量日志为 `unittest-final.txt`；测试发现和执行全程阻断 socket／DNS。`reset-commit-before.txt` 保留修复前失败，`reset-commit-after.txt` 记录阶段回归通过；最终全量包含新增的所有测试。RC2、ADR、CI、16 份历史 Evidence 哈希未变，14 项真实用例仍 PENDING_AUTHORIZATION，暂存区为空，无 Commit／Push。

本次建议提交范围在原代码组增加 mock_api/core.py（代码与测试共 10 文件，文档与清单共 6 文件）；建议 Summary：`fix: linearize fixture publication with audit failure notifications`。本轮未执行提交。

残余限制：真实网络许可、可信材料来源、实际 OS 清理与延迟仍未验收；私有候选分配不等于服务激活；文件完整性检查不提供对恶意并发改写磁盘的原子保证。所有失败都会保留事实，不通过回滚 Fixture 构造或重放请求修补。

## 人工审核阻断问题修复

在原 15 个未提交变更文件上，仅继续修改 supervision.py、coordination.py、test_c3_supervisor.py、本报告和生命周期设计，保留其他修改与所有未跟踪文件。

问题一根因：Supervisor 原先只检查资源清理，未消费协调器的持久化完成状态；协调器失败只回调 revoke，已发出撤权时幂等返回会遗漏新失败。现新增独立完成状态，poll 与 prepare_next 均要求绑定 sidecar 完成并重读核验；失败先锁存再撤权，不恢复 FAILED／RETIRED，不重复请求端点撤权。MemoryEvidence 不构成持久化证明；摘要缺失也不能推断“未派发”。没有新增豁免、重放或许可入口。

问题二根因：check_sidecar 原先只检查报告 audit_gap，漏检 Manifest。现两者均要求显式布尔 false、COMPLETE 完成标志及一致的运行／来源；保留原哈希、事件序号、连接与 action 检查。缺失、类型错误、不一致及读取异常都返回 EVIDENCE_INCOMPLETE。核验只证明离线一致性，不证明来源真实性。

先加入回归测试，修复前 42 项 Supervisor 测试出现 12 个失败（包括 subTest），复现审核问题；修复后再补报告标志、Manifest 写入失败及锁外核验检查。**当前全量 227 项通过：原 217 项保留，本次新增 10 项；C-3C 新测试共 45 项。** 下文 217／35 是首次交付的历史结果。

回归覆盖：缺摘要且双端清理、撤权后 emit／finish 失败、Manifest 写入中阻止重置及完成后允许、内存完成不算核验、STOPPED 后文件篡改、Manifest 审计标志和来源／完成标志、报告审计标志即使重算哈希仍拒绝，以及核验不持 Supervisor 状态锁。

最终验证：整个 unittest 过程阻断 socket 与 DNS；16 份历史 Evidence、RC2、ADR、CI 哈希不变；14 项真实用例仍 PENDING_AUTHORIZATION；暂存区为空。未派发动作的 Controller 证明豁免尚未实现，缺摘要时保守阻止重置；真实存储持久性、来源核验、OS 行为仍未验收。

审核输出目录保留 `blocking-regression-before.txt`，更新 `unittest-final.txt`、`validation.json`、`git-summary.txt` 和包含全部新增文件的 `P3-c3-supervisor-review.diff`。原建议提交分组不变，本轮未执行提交。

## 交付与变更清单

修改 7 个文件：

- `src/p3_core/http/live.py`：只读、非阻塞生命周期观察，不代替 I/O 所有者关闭资源。
- `src/p3_core/mock_api/adapter.py`：在原有限解析成功后返回已校验 action_id，旧 bytes 接口兼容。
- `src/p3_core/mock_api/service.py`：连接摘要交付回调、递增摘要序号、清理／审计观察；发送／撤权短 gate 保留。
- `src/p3_core/delivery.py`：四个离线只读检查命令，没有网络执行入口。
- `README.md`：当前候选状态、设计与审核链接。
- `eval/P3_c3_authorization_checklist.md`：保留原许可范围，补充离线摘要接口进展及机器清单。
- `eval/P3_requirement_traceability.md`：C-3C 增量映射，保留原表与历史数量。

新增 8 个文件：

- [supervision.py](../src/p3_core/supervision.py)：不可重开的监督状态机与可信宿主接口。
- [coordination.py](../src/p3_core/coordination.py)：有界独立 sidecar、关联／缺失检查、失败回调。
- [preflight.py](../src/p3_core/preflight.py)：只读材料诊断，始终不授予执行权。
- [acceptance.py](../src/p3_core/acceptance.py)：14 项计划与人工结果格式。
- [test_c3_supervisor.py](../tests/test_c3_supervisor.py)：35 项确定性无网络测试。
- [生命周期设计](../design/P3_supervisor_lifecycle.md)：状态、锁、接口、取舍与失败规则。
- [机器清单](../eval/P3_c3_acceptance_manifest.json)：14 项稳定名称、范围、前置、离线关联、证据要求、判定与待授权状态。
- 本审核报告。

未修改 Python Controller、HTTP machine、LocalRegistry、RC2、CI、历史 Evidence 或 ADR 正文与状态。历史三份未跟踪 Evidence 继续保持未跟踪，不纳入交付差异。

## 核心设计与人工审核重点

监督者只协调生命周期：绑定精确 run／fixture／范围摘要／授权版本／generation，顺序请求两个已有 gate 撤权，然后观察所有者清理。没有许可生成、网络启动、重放或替代 Controller 的入口。失败后不能恢复，旧运行不能改绑为新运行。两端确认清理且监督审计完成后才能准备新夹具；单独 invalidate 不算撤权。

需要人工重点审查三项设计：

1. 双端撤权采用两个独立生效点，没有跨端原子性；监督者锁不跨组件调用。真实试跑必须分别核对两个 gate 及其间窗口，不能宣称已发字节可撤回。
2. 摘要同步交付在服务 gate 外完成，并在交付结束前阻止后续连接替换记录。慢／挂起的存储会阻止后续连接及清理完成，但不阻止 revoke 生效；默认清理观察超时为 5 秒，仅是工程参数，不是 RC2 预算变更或实测接受值。
3. 新 sidecar 仅用于本轮离线生命周期模拟，固定 NO_NETWORK_SIMULATION。真实端到端可信采集与来源确认仍需后续宿主驱动审核，不能直接把它的 CORRELATED 用作真实用例通过证明。

ADR-001～004 保持 Accepted；ADR-005 保持 Proposed。本轮取舍写入设计文件等待审核，没有自动修改任何已接受架构决策。

## 证据与失败规则

服务端摘要关联 connection／action，可信宿主再附加 run／fixture／generation／scope。action 从 Controller 的已允许动作集合登记，不接受 Planner 自称授权。摘要仅含固定标识、字节计数、首末发送序号、撤权请求／生效信息、原因码、清理标志与递增序号。

客户端记录与 sidecar 分别保存。完全相同重复交付幂等；错配、覆盖造成的序号缺口、丢失、重复冲突、关闭失败或审计故障标记 UNKNOWN／EVIDENCE_INCOMPLETE。部分发送后不推断成功，协调报告始终 INCONCLUSIVE。连接结束时尚未发生的撤权字段为 null，不事后伪造；未来真实验收须另保留两端生命周期观察。

临时 JSONL／Manifest／报告采用唯一目录与哈希关联；本轮不写历史 evidence 目录。完整性检查不等同真实性证明。文件及哈希一并被替换、存储未落盘、进程崩溃后的 I/O 所有者状态，仍需真实环境独立核验。没有自动重试或补发。

## 授权流程与 14 项验收

预检区分 MISSING、INVALID_FORMAT、CONFLICT、SOURCE_UNVERIFIED、RUN_BINDING_PENDING。齐全 JSON、approved_by、active=true 或测试替身都不能产生执行权。只读可信查询即使观察到既有人工核验记录，也仍返回 PENDING_AUTHORIZATION；最终许可保持原 LocalRegistry 语义。

当前仍缺：目标所有者／正式受托者原始许可和委托链，教师目标与测试目录原始记录、可信核验者及来源证明，实际实例／凭据／精确配置版本绑定，预算与撤权责任记录，异常注入单独许可，以及实际 OS 资源／延迟接受条件。工程审核不替代这些许可。

14 项均保持 PENDING_AUTHORIZATION，结果字段为空。支持六种管理状态，但只读工具不自动提升到 VERIFIED；外部结果格式校验也不认证来源。原 [真实集成状态文件](../eval/P3_http_integration_status.json) 未修改。

## 测试结果与失败记录

标准复现命令：

```powershell
$env:PYTHONPATH = 'src'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m unittest discover -s tests -v
```

本地结果：**217 项全部通过，原 182 项继续通过，新增 35 项**。最终额外在整个测试发现和执行期间统一阻断 socket、create_connection、getaddrinfo、gethostbyname、gethostbyname_ex；所有连接与时序测试使用替身，不发实际 HTTP。

新增覆盖双端撤权顺序与同时请求、清理／审计竞争、关闭失败、超时、旧绑定、重置竞争、摘要覆盖／错配／重复／丢失、部分发送未知、落盘后篡改、敏感字符串拒绝、许可材料不足和只读 CLI。服务回调阻塞时单独线程仍能完成撤权。原 182 项测试与断言未删改。

首次执行 213 项时出现 1 个新增测试错误：测试调用 AuthorizedHttpRun 时把 keyword-only 参数写成位置参数。仅修正测试构造方法后通过；随后补 4 项服务交付与清理审计竞争测试，总数 217。无安全断言降级或跳过。文档初次链接检查报告本审核文件尚未创建，交付前创建后复查。

完整日志、验证摘要、基线哈希与完整 Git 差异放在本次任务输出目录 `D:\codex\2026-10-12\referenced-chatgpt-conversation-this-is-an\outputs\c3-supervisor`，不混入运行 Evidence 或 Git 暂存区。

## 需求覆盖与未完成范围

| 状态 | 范围 |
| --- | --- |
| 本轮离线实现与测试完成 | REQ-001／002／007～012 的许可与监督子场景；REQ-014～017 证据子场景；REQ-018 夹具生命周期；REQ-019 只读工具 |
| 部分完成 | 双端真实采集的静态接口与验收计划；取消／清理仅证明模拟调用顺序 |
| 未执行 | REQ-013 真实响应获取；所有 14 项 HTTP 集成；真实 OS 资源关闭、调度和延迟；REQ-021 真实策略实验；正式课程验收 |

未变更 RC2 的 22 个需求编号、要求强度、三计数、预算、NO_NEW_EVIDENCE 或撤权不变量。协调记录数量不是 request_count，fake 发送不是实际请求。已有 36 次离线策略实验未重跑或改写。

## 提交建议与停止点

建议人工审核后分两批：

- 代码与测试 9 个文件：4 个修改源码、4 个新增组件、1 个测试文件。Summary：`feat: add offline lifecycle supervision and evidence coordination`。
- 文档与清单 6 个文件：README、设计、许可清单、追踪表、机器清单、审核报告。Summary：`docs: prepare C3 supervised integration acceptance review`。

本轮不执行提交或推送。真实运行仍受许可和目录阻塞；这些阻塞没有被示例字段或离线测试解除。完成交付后停止，等待人工代码审核。
# 最新增量审核材料：可信 action 登记 P1 与报告状态 P2（2026-10-22）

本节取代下文历史轮次中的最新测试数量描述，历史说明保留。当前仍为未提交候选成果，等待人工代码审核；没有 Commit、Push 或真实 HTTP 操作。

## 根因与修复

P1：原核验只核对文件长度、哈希、序号及部分绑定，未将事件 action 与原始批准动作、原始连接映射对应。修改 action 并重算哈希后仍能通过。修复分两层：报告显式保存预期动作集合及完整最小连接映射，Manifest 引用报告哈希和 run/fixture/generation/scope/授权版本；每条事件使用封闭类型规则并核对全部映射。运行时再与落盘前保留的原始报告和实际离线 Controller 登记快照比较，而不是信任 sidecar 自己提供的摘要。

`capture_controller()` 从精确类型 `SimulationRun` 的批准槽读取 action/check/attempt，验证 run、fixture、scope、版本与审计状态。普通列表、Planner 声明、摘要或完整的自洽文件都不构成独立信任根。`check_sidecar()` 的结构一致结论始终带 `SOURCE_UNVERIFIED` 与 `source_verified=false`。没有 Controller 根时协调器不会 VERIFIED，Supervisor 不会提交 Fixture。真实执行主体认证仍未实现；不能将本轮离线 Controller 的登记核验解释为真实授权或网络验收。

P2：公开报告原来固定返回 PENDING。现区分未完成、写入后待核验、离线核验完成、来源未核验、证据缺口和审计失败。公开成功状态明确为 `OFFLINE_VERIFIED`；真实验收六种状态及 API INCONCLUSIVE 语义均不变。

未派发动作目前没有可信非执行证明的适配路径，保守阻止 Fixture 切换；没有通过伪造服务端摘要补齐。无 action 的合法生命周期事件只存在于独立 Supervisor 审计流，不允许其作为 sidecar 动作事件。

## 本轮实际修改

- `src/p3_core/coordination.py`：Controller 登记快照、原始映射、落盘交叉核验、报告状态。
- `src/p3_core/supervision.py`：只澄清登记接口的信任说明；未改动准备、提交或失败通知代码。
- `tests/test_c3_registration.py`：新增 20 项回归，包含实际落盘改写及重算哈希。
- `tests/test_c3_supervisor.py`：保留全部 55 项旧测试和断言；其中三个成功核验场景改用真实离线 Controller 批准动作，替代手填 action 的旧夹具。
- `design/P3_supervisor_lifecycle.md`：补充数据流、信任边界、失败关闭及公开状态。
- 本审核报告。

## 验证与失败记录

修复前四项最小回归全部失败：null action、未登记 action、缺少 Controller 根仍放行 Fixture、完成后报告仍 PENDING。修复后新增 20 项通过，全量 **257 项通过（原 237 + 20）**；无 skipped、expected failure 或隐藏失败。中间新增测试误读 Controller 的计数器字段导致一次 KeyError，已改为现有 `counts` 接口；没有修改产品计数逻辑或削弱断言。

原独立审核的 12 种确定性时序按原断言重跑全部通过，仅将成功路径的手工 action 夹具替换为实际离线 Controller 根。记录包含实际 Fixture 构造次数、正式提交次数、代次、失败／提交序号和旧绑定失效状态。测试发现及执行全程阻断 socket、连接及 DNS，所有模拟请求与实际 request_count 分离。

交付文件位于任务输出目录 `D:\codex\2026-10-12\referenced-chatgpt-conversation-this-is-an\outputs\c3-supervisor`：`registration-before.txt`（修复前失败），`unittest-final.txt`（全量日志），`registration-reset-races.json`（12 时序），`validation.json`（保护与链接检查），`P3-c3-supervisor-review.diff`（含全部新增文件的完整差异），`git-summary.txt`（实际清单）。

RC2、ADR-001～005、CI 与 16 份历史 Evidence 的基线哈希一致。14 项真实验收继续 PENDING_AUTHORIZATION。CLI 没有增加网络或信任升级入口。暂存区为空，三份历史未跟踪 Evidence 保持未跟踪并排除在完整差异之外。

## 剩余风险与人工审核重点

内存登记根依赖可信 Python 宿主，不能防御恶意宿主改写私有状态；没有持久化来源认证，重启后仅有文件必须重新保持 SOURCE_UNVERIFIED。真实 Controller／服务端来源适配、可信未派发证明、实际许可及教师目录仍待落实。本轮不能证明真实 OS I/O、资源关闭与网络撤权行为。

请重点复核离线根与真实许可的区分、完整文件替换仍被原始报告拒绝，以及重置提交机制没有改变。建议人工批准后将本节六个文件与此前未提交 C-3C 文件一并纳入审核范围；可使用提交说明 `fix: bind offline sidecar verification to controller registrations`。本轮不执行提交。

# 最终定点修复：缺失 sidecar 不得提交 Fixture

最新结果：**258 项 unittest 全部通过，原 12 种确定性重置竞争时序全部通过**。无 skipped、expected failure 或隐藏失败。下文 257 项等为前轮历史记录。

本轮 P1 根因是 `_evidence_status()` 将未绑定协调器直接当作 VERIFIED。最小回归使用 FakePort、双端清理和实际 Fixture 工厂计数，在旧实现上失败；修复后反复 prepare_next 均拒绝，工厂调用和正式提交次数均为 0，旧绑定不失效。

修复仅将缺失协调器返回值改为 MISSING，并明确允许纯清理观察在 MISSING 时进入 STOPPED。STOPPED 不等于证据完成：原 prepare_next 的 VERIFIED 门槛会在任何 Fixture 分配前拒绝。没有增加例外开关、许可入口或改变已绑定 sidecar 的核验要求。

本轮修改四个文件：`src/p3_core/supervision.py`、`tests/test_c3_supervisor.py`、`design/P3_supervisor_lifecycle.md`、本报告。新增 1 项最小回归；13 项原先无 sidecar 的重置／竞争测试改用实际离线 Controller 批准、独立登记快照、临时 JSONL/Manifest 和完成核验，原断言保持。原 257 项均继续通过。

任务输出目录中的 `missing-sidecar-before.txt` 保存修复前失败，`missing-sidecar-after.txt` 保存最小回归通过；`unittest-final.txt` 是全量日志，`registration-reset-races.json` 是 12 种时序记录，`P3-c3-supervisor-review.diff` 包含全部未提交 C-3C 新增文件。

测试发现和执行期间阻断 socket、连接及 DNS。28 个受保护文件哈希不变（包括 16 份历史 Evidence、RC2、ADR 和 CI）；14 项真实集成继续 PENDING_AUTHORIZATION。Controller 及真实许可未改动，暂存区为空，未 Commit 或 Push。候选修复等待人工复核，不代表真实网络或正式课程验收通过。
