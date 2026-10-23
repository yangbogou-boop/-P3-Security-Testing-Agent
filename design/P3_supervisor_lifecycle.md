# 最新验证数量

当前候选为 **258 项无网络测试及 12 种重置竞争时序通过**。文中的 227、237 等数量为历史阶段记录，不代表最新测试总数或真实 HTTP 验收。

# C-3C 生命周期监督与证据协调设计

状态：实现候选，等待人工代码审核。本文件不更改 ADR-001～004 的 Accepted、ADR-005 的 Proposed，也不授予网络许可。规范沿用 [RC2](../brief/P3_specification_v1.0-rc2.md)、[授权边界](../brief/P3_authorization_boundary.md) 和 [ADR-004](ADR_004_http_dispatch_and_cancellation.md)。

## 最小组件与责任

| 组件 | 责任与边界 |
| --- | --- |
| `supervision.Supervisor` | 绑定 run、fixture、授权版本、范围摘要和 generation；双端撤权、观察清理、禁止旧实例复用；没有 start、dispatch 或许可生成入口 |
| `LifecyclePort` | 可信宿主适配现有 AuthorizedHttpRun／AuthorizedService；核对原绑定与凭据摘要，仅暴露撤权、观察、作废及动作登记 |
| `coordination.EvidenceCoordinator` | 接收已校验服务端摘要，关联可信宿主从 Controller 读取的 action；独立 JSONL／Manifest／报告，不改客户端源记录 |
| `preflight.authorization_preflight` | 只读材料诊断；不调用 LocalRegistry 发放快照、不改变其真实许可语义 |
| `acceptance` | 14 项稳定用例的前置、证据与人工结果格式；无执行器、无自动 VERIFIED |

复用原 Controller、Executor、FixtureManager、响应解析器和 JsonlEvidence。范围摘要覆盖精确目标、版本、预算、身份与候选集合，授权版本另行显式绑定。generation 为监督记录世代，不能替代客户端内部的派发生命周期计数。

## 生命周期与锁

`BOUND → STOPPING → STOPPED → RETIRED`；故障进入 `FAILED`。FAILED、RETIRED 不可恢复；STOPPED 只能准备一个新夹具，不能恢复旧运行。新夹具仍需新配置绑定、许可核验和新的 Supervisor，不继承执行权。

1. 可信宿主构造匹配的两端生命周期接口；已撤权或失败对象拒绝再次绑定。普通 Planner 不取得 Supervisor／Registry 引用。
2. `revoke()` 在监督者自己的短锁内不可逆地登记请求，然后释放锁，依次调用两端原有撤权 gate。提供两种顺序供确定性测试；不是跨进程或跨端原子事务。第一端生效至第二端生效之间的窗口必须分别观察，不能声称同时生效。
3. 每个端点的 send 与 revoke 线性化仍由原 gate 决定。监督者不在一个组件锁内调用另一个组件，不在 gate 内等待 I/O／磁盘。已进入内核的字节不能撤回。
4. I/O 所有者继续负责关闭。`poll()` 只观察，客户端忙时返回未清理；监督者不代替其他线程关闭资源。不完整清理保持 STOPPING；超时、时钟回退、关闭失败、观察异常或审计失败进入 FAILED。
5. 两端撤权、清理及监督审计都完成后，若绑定协调器，还必须通过协调器完成核验才公开 STOPPED。并发 poll 不等待另一次观察；撤权审计、清理审计或 sidecar Manifest 未完成时不能重置。
6. `prepare_next()` 先独占预约准备资格（不是 RETIRED／提交），复核两端清理并在锁外构造私有候选。完成证据复核和准备审计后，才在短锁内发布候选引用并进入 RETIRED。旧绑定失效在提交后、锁外执行。单独 invalidate 不是撤权。并发重置最多一个提交；失败需人工处置，不自动重试。

清理超时默认 5 秒是监督者观察参数，独立于 RC2 检查预算，不延长 90 秒试跑预算。它不提供硬实时保证，也不会强杀 Python 线程。可信宿主必须持续调度 poll 和 I/O 所有者；本轮不提供实际网络驱动入口。

## 重要取舍与重新评估

选择“两个短 gate 顺序撤权＋所有者清理观察”，不引入跨端大锁。大锁可能把阻塞关闭／审计延迟传播到撤权入口，且不能撤回已发送字节。代价是存在两个生效时刻，需要分别保存和审核；真实 OS 取消延迟仍待许可后测量。

选择“连接结束后同步交付有限摘要，再接纳下一连接”，不新建后台无限队列。后台队列增加丢失、溢出和 shutdown 排序问题。回调在服务 gate 外，`_handling` 保持为真，确保摘要不被覆盖。代价是慢存储会延迟下一连接及清理完成；撤权仍可生效，监督者可超时进入 FAILED，但不会假称存储线程已终止。

以上为本轮待审核实现选择，未另建重复 ADR。若实际存储延迟无法满足试跑观察值、需要并发服务／跨进程监督或持久化真实性证明，应重新评估并记录 ADR；不能直接扩大现有架构。

## 双端证据契约

服务端新增 `handle_with_action()`，仅在完整有限请求通过原业务解析后返回 action_id。摘要包含 connection_id、action_id、接收／发送字节数、首末发送 gate 序号、撤权请求／生效时间及序号、固定原因、清理失败、单调 summary_sequence。没有原始头、Token、正文、异常文本或堆栈。

可信宿主在 Controller prepare 后、下一次 I/O step 前调用 `register_actions()`。服务端摘要只与这一集合、run_id、fixture_instance_id、scope_digest、generation 绑定；这不是根据不可信响应猜测关联。不能确认的 action 标 UNKNOWN；缺失、重复冲突、序号跳跃、跨运行错配、容量超限标 EVIDENCE_INCOMPLETE。完全相同的重复交付幂等，不能增加连接数。默认 32、最大 256 条是协调记录容量，不改变检查预算。

记录放在独立唯一 sidecar 目录，JSONL 的 hash 和长度、报告 hash 进入 Manifest。`evidence-check` 有界读取并核对摘要格式、序号、绑定、关联和文件一致性；它不证明来源真实性，也不能识别攻击者同时重写数据及全部哈希。真实环境的可信目录访问控制、持久化故障观察和独立复核仍必需。

本轮 sidecar 固定标记 `NO_NETWORK_SIMULATION`，实际双端网络证据采集未验收；不得将它作为真实验收源。客户端 JSONL／Manifest／有限报告继续独立存在，不被合并覆写。关联成功只是 CORRELATED，不是 PASS。部分发送后为 UNKNOWN；协调报告始终 INCONCLUSIVE。保存失败触发双端撤权，未完成记录不得通过重放补齐。汇总关闭后不能追加；旧／迟到摘要拒绝。

### 人工审核后的完成门槛修订

协调器 `completion_status()` 与内存 CORRELATED 分离：PENDING 表示尚未结束或正在写入；UNVERIFIED 表示已结束但缺少可核验文件（包括 MemoryEvidence）；INCOMPLETE 表示关联缺口／冲突；AUDIT_FAILED 表示写入或落盘一致性核验失败；VERIFIED 仅表示本轮离线 sidecar 文件一致性核验通过，不表示来源可信或 HTTP 验收通过。

`finish()` 关闭追加后，写出带 COMPLETE／INCOMPLETE 标志的报告与 Manifest。只有 JsonlEvidence 的文件被重新读取，匹配本次完成报告、哈希、运行及来源标识、完整性标志、事件顺序和关联，才可返回 VERIFIED。Manifest 与报告均必须显式含布尔 `audit_gap=false` 和 `completion=COMPLETE`；缺失、非布尔、冲突或异常均失败关闭。

绑定协调器的 Supervisor 在 poll 和 prepare_next 分别检查完成状态。PENDING 继续等待且禁止重置；不完整、审计失败或不可信完成状态将失败锁存。失败通知不再仅调用幂等 revoke，而先锁存失败，再保证两端撤权已请求，因此撤权之后的新审计错误不会丢失。文件读取、写入、审计回调和端点操作均在 Supervisor 状态锁外执行；准备新实例前再次复核文件，不能只信任先前的 STOPPED。

未收到摘要的已登记 action 不自动豁免。本轮没有实现由可复核 Controller 未派发证据驱动的豁免路径，故这种情况保守阻止重置并交人工处理，不伪造摘要、不重发。文件一致性读取不是原子防篡改或断电持久化保证；可信存储访问控制和真实环境的持久化观察仍是后续要求。

### Fixture 重置提交点修订

已确认原 FixtureManager.reset() 只生成 UUID、合成凭据和独立不可变 Fixture，没有全局当前实例、注册表写入或服务切换。新增 `FixtureManager.prepare()` 提供同一纯构造逻辑；原 reset() 保留为兼容工厂。Supervisor 不再调用 reset()，候选生成在锁外完成。准备可能分配内存、消耗随机数，但不发布实例、不改变旧 generation、不启动服务；失败时丢弃私有对象，不宣称撤回已经完成的对象分配。

**正式线性化点**是 Supervisor 状态锁内的一组有限内存赋值：增加排序序号、保存提交序号／次数／实例 ID、发布 `_next_fixture`，并置 RETIRED。这里没有工厂调用、文件读写、审计回调、端点操作、等待或清理。失败通知 `_latch_failure()` 使用同一短锁，先记录首次失败序号，再置 FAILED 并撤下候选引用；重复失败保持锁存，不抹去首次序号或提交事实。

| 可验证先后顺序 | 实际构造／正式提交 | 结果 |
| --- | --- | --- |
| 端点复核暂停时失败先生效 | 0／0 | 不作废旧绑定；旧 generation 不变；FAILED |
| 私有候选已准备，失败先于提交生效 | 1／0 | 不发布候选、不作废旧绑定；丢弃私有候选；FAILED |
| 准备审计写入失败 | 1／0 | 同上，禁止通过重试再准备 |
| 提交先于失败通知生效 | 1／1 | 保留 commit_sequence < failure_sequence 和实例 ID；撤下候选；FAILED；不谎称未提交 |
| 两线程同时准备 | 最多 1／最多 1 | 准备资格仅授予一个线程，另一线程拒绝 |

排序针对“失败通知取得协调锁并生效”，不把磁盘故障实际发生时间等同于通知生效时间。通知与提交共享一个边界，比在多处读取 audit_failed 更强。外部审计、文件核验及失效操作仍在锁外；若提交后审计或失效失败，提交历史不回滚，调用者收到失败，运行不可重开。失败先于提交时在同一边界阻止发布，不依赖事后异常抵消副作用。

报告新增 reset_commit_count、reset_commit_sequence、failure_sequence、committed_fixture_id、committed_generation 与 next_fixture_available；生命周期审计事件记录提交／失败序号。committed_generation 只是新候选的监督世代，不改旧绑定和 Controller 的 generation。next_fixture_available 只表示候选引用可用，**不是 HTTP 服务激活或真实许可**。提交后返回的对象依旧要通过新配置、真实许可和宿主绑定才能用于后续运行；本轮没有网络激活接口。

新测试通过实际 Fixture 构造函数计数及提交计数验证上述边界，并验证构造、审计和旧绑定失效均不持 Supervisor 状态锁。原 227 项测试不变，新增 10 项，本地 237 项通过。

## 只读预检与人工核验

输入包括严格 HttpConfig、owner／teacher_catalog 材料元数据、fixture_binding、预算记录、撤权责任、试验范围和单独异常注入范围。材料元数据含来源／引用／摘要、角色／主体、委托引用、授权版本、范围摘要、有效期。完整格式不等于材料真实。

诊断类别：MISSING、INVALID_FORMAT、CONFLICT、SOURCE_UNVERIFIED、RUN_BINDING_PENDING。可信宿主可提供只读人工复核记录查询，按材料元数据摘要查验；CLI 不提供这个参数或 approved 开关。查询成功只表示此前人工核验被观察到，仍返回 PENDING_AUTHORIZATION、execution_allowed=false；真正材料内容、委托链、只读快照及最终运行绑定必须通过原 LocalRegistry 与可信宿主流程完成。

机器清单见 [14 项验收记录](../eval/P3_c3_acceptance_manifest.json)。允许的管理状态不替代 ALLOW/DENY、执行状态或 API 结论。外部结果格式检查不认证来源；离线工具永远不提升为 VERIFIED。

## 离线入口

设置 `PYTHONPATH=src` 后：

```text
python -m p3_core.delivery supervisor-plan
python -m p3_core.delivery authorization-preflight material-draft.json
python -m p3_core.delivery integration-status
python -m p3_core.delivery evidence-check temporary-sidecar-directory
```

以上命令只读，不启动 listener 或 Executor；输入错误不回显原始内容。缺少真实材料是正常待授权状态，不是测试通过。详见 [许可清单](../eval/P3_c3_authorization_checklist.md) 和 [审核报告](../review/P3_c3_supervisor_review.md)。
# P1/P2 补充：可信动作登记与文件核验（2026-10-22）

本节补充此前生命周期设计，不改变 Fixture 准备／短锁提交、失败通知排序或 Controller 授权语义。

数据流为：实际 `SimulationRun` 的独立 Controller 批准候选 → 可信宿主调用 `capture_controller()` → 在 Controller 锁下读取 action/check/attempt 的不可变元组及当前配置绑定 → 协调器保留独立内存登记根 → 接收并复制连接摘要 → 写入事件、包含动作集合及连接映射的报告、引用报告哈希及完整绑定的 Manifest → 核对文件内部一致性 → 与写入前保留的报告、登记根和原始连接映射比较。

`expect()` 和 `Supervisor.register_actions()` 仅声明期望关联，不能单独产生可信登记依据。核验入口不接受 JSON 登记根、调用者自算摘要或 `trusted=true`。`capture_controller()` 只接受精确类型的实际离线 Controller，核验 run、fixture、scope、授权版本和 Controller 审计状态；只读取已 ALLOW 且属于批准候选集的动作。不改变批准规则，也不赋予网络许可。generation 是监督者绑定的生命周期代次；它与其他绑定字段一同固定在报告及 Manifest，并在每条事件和运行时原始报告之间逐一核对。

三层结论明确分开：

| 层次 | 本轮能力 |
| --- | --- |
| 文件内部一致性 | `check_sidecar()` 可返回 `CONSISTENT_OFFLINE_SIDECAR`，同时明确 `registration_status=SOURCE_UNVERIFIED`、`source_verified=false`；自洽文件不是独立信任根 |
| 与独立离线 Controller 登记一致 | 协调器在上述内存根、原始报告及连接映射均匹配后，内部完成状态可为 `VERIFIED`；公开报告明确为 `OFFLINE_VERIFIED` |
| 真实执行主体来源认证 | 本轮未实现；真实 HTTP 用例继续 `PENDING_AUTHORIZATION`，不能由离线登记根或 sidecar 获得真实来源认证 |

Python 宿主及 Controller 内部状态是信任边界；本方案不抵抗可任意修改同进程私有字段或替换 Python 代码的攻击者。不从文件恢复信任根；进程重启后仅凭文件不能重新获得 VERIFIED。真实 `AuthorizedHttpRun` 尚无本适配器支持的独立来源路径，失败关闭，不能拿模拟 Controller 代替真实来源。

sidecar 只允许 `server_summary` 动作事件，action 必须为已登记字符串，不能为 null。生命周期事件仍在 Supervisor 独立审计流中，不要求 action，也不得冒充连接摘要。每个登记动作必须恰有一个连接摘要；连接、动作、事件 ID、连续序号、完整绑定、内容及审计标志均交叉核对。此版本没有可信未派发证明适配器，因此无摘要的登记动作仍阻止切换，不伪造摘要填补。

公开 `report().completion` 区分 `PENDING`、`FINALIZING`、`WRITTEN_UNVERIFIED`、`OFFLINE_VERIFIED`、`SOURCE_UNVERIFIED`、`EVIDENCE_INCOMPLETE` 和 `AUDIT_FAILED`。落盘 `COMPLETE` 仅表示文件生成阶段完成；不是公开的来源核验结论，也不改变六种真实验收管理状态。

所有磁盘读取、写入及 Controller 快照读取仍在 Supervisor 短锁之外。核验失败通过已有失败通知入口锁存；提交点和通知的线性化排序保持原实现。文件篡改只有被检查时才能发现；不能据此承诺外部存储修改具有即时通知。

# 无 sidecar 的清理观察与重置门槛（2026-10-22 最终补充）

`EvidenceCoordinator` 未绑定时，`_evidence_status()` 返回 `MISSING`，绝不返回 VERIFIED。双端确实撤权、清理完成且没有失败时，纯生命周期观察仍可进入 STOPPED；这里的 STOPPED 只表示清理已观察完成，不代表证据核验成功或允许切换 Fixture。

`prepare_next()` 仍首先要求独立核验状态为 VERIFIED。MISSING 在分配、失效旧绑定和正式提交之前拒绝；重复调用也不能绕过。不能在 STOPPED 后补绑协调器重新开放运行。已有 sidecar 的 PENDING、SOURCE_UNVERIFIED、审计失败和其他失败关闭语义不变，准备／提交分离及短锁线性化点不变。

纯撤权无需 sidecar，但任何 Fixture 正式提交都需要它。人工列表、Planner 声明和单独的生命周期审计回调不能替代 Controller 登记、完整 sidecar 与落盘核验。
