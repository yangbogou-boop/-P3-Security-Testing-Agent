# C-3 真实集成许可核验与验收卡

C-3C 增量：新增 [机器可读 14 项清单](P3_c3_acceptance_manifest.json) 与 [只读预检／监督设计](../design/P3_supervisor_lifecycle.md)。所有用例仍待授权。服务端现在支持在下一连接前向可信消费者交付摘要；下文“仅保存最后摘要”是 C-3A/B 原限制，已补离线交付接口，但真实持久化、可信源、OS 资源及双端时间观察仍未验收。原审批状态、目录范围和用例名称不变。

状态：**PENDING_AUTHORIZATION**。本文件不含批准记录，不构成实际执行许可。沿用 [14 项状态](P3_http_integration_status.json)、[RC2](../brief/P3_specification_v1.0-rc2.md)、[授权边界](../brief/P3_authorization_boundary.md) 和 [ADR-004](../design/ADR_004_http_dispatch_and_cancellation.md)，不改变稳定需求及强度。

## 共同前置条件与许可字段（全部待取得／核验）

| 核验项 | 必须填写并核对的真实材料 | 当前状态 |
| --- | --- | --- |
| 目标许可 | authorization_id、authorization_version；目标所有者或正式受托人身份、委托链、原始材料来源／引用／内容摘要、生效与失效时间、明确只读范围 | 待取得，不能以姓名／active=true 代替 |
| 教师目录 | catalog_record_ref、批准材料来源／摘要、教师批准的目标／端点／身份／检查目录、版本与适用时间；与目标许可取交集 | 待取得，不以本轮技术审核替代 |
| 可信核验 | 指定核验者、核验时间、证据可访问性；LocalRegistry 的 owner_ref／catalog_ref／必要 delegation_ref、registry_ref、scope_digest 与只读材料快照 | 待核验；摘要不证明批准真实性 |
| 精确范围 | scheme=http、host=127.0.0.1、明确 port；三个 GET 端点、有限路径／查询组合、六项候选及合法对照；禁止任意 URL／附加头／代理／重定向／重试 | 待绑定实际实例，不能从示例配置取得执行权 |
| 夹具与凭据 | fixture_instance_id、contract／matrix／candidate／fixture 版本；监督记录引用，实际生成凭据集合的本地摘要，身份角色与对象归属 | 待监督者绑定；不保存原始凭据；重置先撤权再换实例 |
| 预算及撤权 | budget_version、max_checks、logical_timeout_seconds、concurrency、trial／冻结状态和依据；撤权操作者、可信入口、generation 与失效通知流程 | 8／90／1 仍为试跑；班级冻结按原治理规则 |
| 故障试验许可 | 明确允许的连接故障、错误响应、超时、撤权时序、审计故障与资源关闭试验；只在隔离合成数据夹具内注入 | 待在实际试验计划中批准；不得默认扩大目录 |
| 执行前检查 | 人工审核本轮实现；确认本地端口对应获准夹具、服务和 Executor 的绑定相同；预先定义取消／关闭延迟指标与接受值 | 待真实环境核验，无测量值或通过声明 |

普通代码修复、测试设计由负责人决策；实际目标许可、课程目录及最终冻结／正式验收继续遵循各自阶段，不扩大为所有开发的教师前置审批。

## 共同判定与最小证据

- Controller ALLOW／DENY、执行状态、API PASS／FAIL／INCONCLUSIVE 分列。已识别响应头只证明响应事实。正确负向拒绝必须与同实例合法对照成功关联；完整关联的受保护 JSON 泄露才可确认 FAIL。
- 缺失／非法 JSON、重复长度、错误实例、截断、未持久化证据不得凭 canary 确认 FAIL。完整充分的 5xx 泄露按既有契约可同时 FAIL 与 RESPONSE_ERROR，不把这条例外应用于损坏响应。
- 保存 run／proposal／check／attempt／action／connection／evidence ID；许可快照 ID、范围摘要、版本与材料引用；三计数和模型计数；授权决定、固定原因码、发送偏移与 gate 序号、响应头事实、经过封闭 schema 验证的字段／断言、合法对照关联、未覆盖范围；JSONL、Manifest 前缀与报告哈希。
- 服务端 summary 只含连接 ID、接收／发送字节数、首次／末次发送序号、撤权请求时间／生效序号／生效时间、原因和清理失败标志。`last_connection` 是有限内存快照，可信监督者须在下一连接替换它前读取并关联保存；它不是持久化完成标记，不替代客户端 Manifest。
- 禁止记录原始凭据、任意请求参数、异常正文或完整未校验 HTTP。审计不可写时标明缺口，停止，不能通过重发填补。发送与磁盘不是原子事务，未知发送区间记 unknown，不能记零。

## 14 项用例卡（真实执行全部未开始）

以下每项均需上述真实许可／目录／快照／绑定字段；异常注入和撤权变体还需被实际试验许可明确涵盖。表中离线验证只说明控制逻辑测试通过。

| 稳定用例名 | 额外前置与刺激 | 正常／异常判定标准 | 特别需要保存的证据与观察 | 已有离线验证；真实状态 |
| --- | --- | --- | --- | --- |
| GOOD_PAIRED_CONTROLS | Good 新实例，六项批准候选及三个合法对照 | 对照 200＋完整主体／对象／角色断言；匿名 401、越界对象与角色 403＋完整拒绝并关联对照才 PASS；对照异常则负向不能 PASS | 六项范围、同实例关联、响应断言及未覆盖项 | `test_good_all_six_fixed`、`test_good_dynamic_controls_resolve`；PENDING_AUTHORIZATION |
| AUTH_DISCLOSURE | 独立 AUTH 实例，仅 profile 认证缺陷 | 合法资料对照成功；匿名得到完整关联的受保护资料才 FAIL；仅 200 或标记片段不足 | profile 的 action／实例／身份、合成资料字段、对照 | `test_three_defects_both_strategies`；PENDING_AUTHORIZATION |
| BOLA_DISCLOSURE | 独立 BOLA 实例；alice 访问 bob 对象、bob 合法对照 | 完整 obj-b、owner=bob、marker 和关联均成立才 FAIL；错误对象／旧实例不确认 | 对象归属与对照证据；许可只含获准对象组合 | 同上及业务矩阵测试；PENDING_AUTHORIZATION |
| RBAC_DISCLOSURE | 独立 RBAC 实例；member 与 admin 配对 | 低角色获得完整 admin report 才 FAIL；正常拒绝需 admin 对照成功 | period=demo、audience、marker、角色与对照关联 | 同上及业务矩阵测试；PENDING_AUTHORIZATION |
| CONNECTION_FAILURE | 获准本地故障注入，禁止探测其他地址 | ERROR／INCONCLUSIVE、TRANSPORT_ERROR；连接失败不计请求；若先部分发送则保留 1，不重试 | connect／send 顺序、是否正发送、清理结果、unknown 审计区间 | `test_read_timeout_and_transport_failure_no_raw_exception`；PENDING_AUTHORIZATION |
| UNEXPECTED_STATUS | 同实例注入 404／5xx／重定向 | 非预期状态与证据不足为 INCONCLUSIVE＋RESPONSE_ERROR；不跟随 Location；仅完整独立 5xx 泄露可保留 FAIL | 响应完整性、状态、断言、无第二目标派发 | `test_404_and_5xx_no_leak_are_inconclusive`、`test_t35_5xx_complete_vs_truncated_leak`；PENDING_AUTHORIZATION |
| INVALID_JSON | 非法 UTF-8／JSON、重复键、额外字段、重复长度 | INCONCLUSIVE＋RESPONSE_ERROR，不以 canary 翻转；不保存原文 | 固定诊断、长度／完整性事实、已保留的其他完整检查 | `test_t34_canary_cannot_rescue_malformed_framing_or_json`；PENDING_AUTHORIZATION |
| TRUNCATION | 有头缺体、长度不匹配、容量溢出 | 有可识别头保留 EXECUTED 事实，结论 INCONCLUSIVE；按 RESPONSE_ERROR／实际传输故障停止 | headers_received、缺失标志、容量与发送计数、Manifest 缺口 | `test_header_fact_survives_incomplete_body_without_verdict`；PENDING_AUTHORIZATION |
| TIMEOUT | 可控慢读／慢写；预先确定实际截止与观察容差 | 未获响应 TIMEOUT；总预算到点优先 BUDGET_EXHAUSTED；已获头部可保留 EXECUTED，但未完成结论不得升级 | t0／总截止、服务处理截止、停止时间、释放时间、未覆盖项；不宣称硬实时 | `test_budget_before_first_send_blocks_memory_dispatch`、`test_service_timeout_read_and_partial_write_close`；PENDING_AUTHORIZATION |
| REVOKE_CONNECT | 在 connect 前、connect 完成后首写前分别撤权；监督者同时协调服务／客户端 | 撤权生效后不得开始响应／请求发送；connect 不计请求；清理且不重连 | 两侧撤权请求与生效时间、gate 序号、connect 与首写顺序、0 正发送 | 原 HTTP-T27 测试、`test_service_revoke_during_wait_does_not_block`；PENDING_AUTHORIZATION |
| REVOKE_FIRST_SEND | 屏障安排撤权先赢和首写先赢两种顺序 | 撤权先赢：0 新写；send 先赢：已发字节保留，首个正返回计 1，随后不续写；不能撤回已发字节 | first_send_sequence 与 revoke_effective_sequence、请求到生效延迟、内存计数与审计缺口 | `test_service_send_and_revoke_have_total_gate_order`、计数 hook 单元测试；PENDING_AUTHORIZATION |
| REVOKE_PARTIAL_SEND | 部分正发送后撤权／过期／超时 | 不再续写、不重复计数；原连接关闭，未完成为 INCONCLUSIVE；关闭失败明确记录并阻止后续服务发送 | 已发偏移、末次发送序号、生效后写次数=0、关闭结果／延迟 | `test_service_partial_send_then_effective_revoke`、`test_service_close_failure_visible_and_no_more_send`；PENDING_AUTHORIZATION |
| LATE_RESPONSE | 终态后交付旧响应；另测旧凭据与错误实例 | 不复活、不把未完成项升为 PASS；错误绑定不得误确认 overdenial | 终态前后快照、known_action、实例／凭据摘要匹配结果（不存凭据） | `test_late_response_during_read_cannot_upgrade`、服务绑定测试；PENDING_AUTHORIZATION |
| AUDIT_FAILURE | 发送前、正发送后、响应证据前／Manifest 时注入存储故障 | AUDIT_ERROR／audit_gap，停止新派发；当前未持久化断言不确认；前缀恢复 unknown，禁止重放 | 失败阶段、可用前缀、Manifest 缺失／哈希、关闭失败标志、未覆盖范围 | `test_audit_failure_cannot_confirm_response`、原 HTTP-T30；PENDING_AUTHORIZATION |

## 撤权／时间／资源观察卡

真实试跑每个许可涵盖的变体至少三次独立重置（ADR-004），保留所有失败；不通过重复跑到成功来隐藏失败。

1. 分别记录客户端与服务端撤权请求时刻、gate 生效时刻及序号；请求到生效延迟单列，不能把请求到达等同生效。非阻塞 send 与撤权共享短 gate；等待和关闭不持该 gate。
2. 校验生效后的正发送次数与字节数为零。服务端发送字节不是 Agent request_count；Agent 首次正发送仍只计一次，连接和部分续写不多计。
3. 记录预算截止到停止观察的延迟、头部／正文完成性和迟到结果处理。Python／OS 调度不提供硬实时保证；接受容差需实际试验前记录，不在本轮杜撰。
4. 记录关闭请求／完成时间、失败、剩余句柄／端口占用、后续初始化是否被拒绝。单元测试只证明调用顺序，不证明 OS 已释放资源。关闭失败为安全失败，须人工处置，不继续真实试跑。
5. 当前实现仅存服务端最后连接摘要；持久化采集、OS 资源观察和两侧时间关联仍需许可后由可信监督者完成。若不能可靠保存则不得宣称该真实用例通过。
