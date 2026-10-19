# P3 第三阶段第二轮 B：无网络 HTTP 核心审核报告

日期：2026-10-19。状态：实现与本地无网络测试完成，等待人工代码审核；本助手未执行 Commit／Push。执行期间外部操作产生了 73b150d，已保留；剩余修正尚未提交。未进行 HTTP 集成或正式课程验收。

## 1. 仓库与开发边界

实际仓库为 `D:/project/-P3-Security-Testing-Agent`；本轮指令中的 `D:/project-P3-Security-Testing-Agent` 不存在，沿用此前一直使用的仓库。开始时 HEAD 为 74ed7b1，执行 Git fetch 后本地领先 origin/main 1、落后 0，无远程新提交；未合并或覆盖工作区。Git 远程核对是唯一获准联网操作，没有被测 API 请求、socket 服务、外部探测或 LLM 调用。

三份原未跟踪 Evidence 与已有受版本管理的 Evidence 均保留。原 Controller、Planner、模型、Evidence 实现、offline CLI、tests/test_core.py 和 CI 不修改。原设计审核报告 [第二轮 A](P3_http_design_review.md) 按历史记录原样纳入版本管理；其中 Proposed／未实现描述是当时状态，本报告和 ADR-004 当前状态为后续承接。

## 2. 实际交付文件

| 文件 | 作用 |
| --- | --- |
| [http/__init__.py](../src/p3_core/http/__init__.py) | 无网络 HTTP 模块边界声明 |
| [contract.py](../src/p3_core/http/contract.py) | 独立 http-local schema、不可变六项候选、有限端点／身份／权限矩阵、范围摘要 |
| [authorization.py](../src/p3_core/http/authorization.py) | 可信操作者材料接口、权属／委托和目录核验、不可变许可快照；默认拒绝合成许可 |
| [protocol.py](../src/p3_core/http/protocol.py) | 精确 GET 构造、有界 HTTP/1.1／UTF-8 JSON 解析、独立模拟判定 |
| [machine.py](../src/p3_core/http/machine.py) | 单 I/O 所有者 SimulationRun、短 gate、登记／尝试、首写模型计数、预算／撤权、必要对照与有限报告 |
| [transport.py](../src/p3_core/http/transport.py) | 仅内存假传输，无 socket 后端；记录长度和偏移，不记录请求字节 |
| [recovery.py](../src/p3_core/http/recovery.py) | 模拟审计前缀检查，缺发送后记录时标未知、禁止自动重放 |
| [test_http_core.py](../tests/test_http_core.py) | 新增 54 项 unittest，含测试专用许可与 Good／Known Bad 响应构造 |
| [README](../README.md) | 区分离线核心、无网络 HTTP 模型与待实现真实功能 |
| [ADR-004](../design/ADR_004_http_dispatch_and_cancellation.md) | 当前 Accepted，保留历史 Proposed 和原比较，注明只确认技术路线 |
| [HTTP 设计](../design/P3_http_integration_design.md)、[契约](../brief/P3_http_contract_draft.md)、[验收计划](../eval/P3_http_acceptance_plan.md) | 增补实现边界、实际 schema 和 U 子场景状态 |
| 本报告、[原设计审核报告](P3_http_design_review.md) | 本轮审核与历史承接；均非实际 HTTP Evidence |

共 15 个交付路径：5 个既有跟踪文件更新，8 个新源码／测试文件，1 个新增审核报告，1 个原未跟踪历史审核报告纳入版本管理。其中 8 个新增路径已被执行期间的外部提交 73b150d 跟踪；本助手保留该提交。其后的待审核差异为 7 个跟踪文件修改与 2 个新增文件（recovery.py、本报告），暂存供 GitHub Desktop 审核；本助手不 Commit／Push，不暂存历史 Evidence。

## 3. 实现与 RC2 映射

| 需求 | 本轮实现及证据边界 |
| --- | --- |
| P3-REQ-001、002、008、009 | 独立 schema、可信材料接口、范围与版本精确匹配、未知字段／目标／身份／编码拒绝；没有实际执行许可，合成材料只用于显式模拟 |
| P3-REQ-003 | 固定六项确定性计划；独立 Planner 输入只读候选，规划纳入逻辑预算；动态策略尚未实现 |
| P3-REQ-004～006、014、018 | 三类负向及合法对照的纯内存 Good／Known Bad 判断；正确拒绝需对照，过度拒绝需身份依据；不等于真实 API 检出 |
| P3-REQ-007、010、011 | 独立授权入口、短 gate 与单所有者状态机；累计登记／首次尝试、部分写计数、不可重开终态、撤权／预算、防误停 |
| P3-REQ-012、015～017 | 固定错误码、审计失败禁发、唯一关联 ID、最小化 JSONL／Manifest／报告、原始凭据／未批准参数不落盘、未覆盖及模拟来源明确 |
| P3-REQ-013 | **实际 HTTP 获取未实现**；只提供内存响应处理和模型派发，无真实响应证据 |
| P3-REQ-019 | 原 offline CLI 保留；新 HTTP 模型通过 Python 模块和 unittest 使用，没有新增 HTTP CLI |
| P3-REQ-020 | 配置及快照绑定契约／矩阵／候选／夹具／预算版本，报告模型计数和未覆盖；完整策略实验元数据与成本比较待后续 |
| P3-REQ-021／022 | MUST 固定／动态比较尚未做；MAY 真实 LLM 不接入，未修改要求强度 |

`plan_count`、`attempt_count` 保持累计规则，`request_count` 始终 0。`model_request_count` 专门表示内存假 send 首次返回正数，部分续写不重复计，不能把它算作 RC2 实际请求数。运行报告 `execution=NOT_EXECUTED`、API `conclusion=INCONCLUSIVE`；只有 `simulated_conclusion` 表示对已知模拟字节的算法结果，并统一标 NO_NETWORK_SIMULATION。

## 4. 实际自动化结果

环境：Windows、Python 3.9.12、标准库 unittest。在仓库根目录执行：

```powershell
$env:PYTHONPATH = 'src'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m unittest discover -s tests
```

最后一次全量运行：**103 tests，0.899s，OK**；原有 49 项全部通过，新增 54 项通过。新测试逐用例禁止 socket、create_connection、getaddrinfo，产物仅在临时目录；本轮没有运行 HTTP 集成或调用真实 LLM，也未重新验证远程 Actions。耗时是本次本机记录，不是性能达标承诺。

| 验收子场景 | 对应测试函数／内容 |
| --- | --- |
| HTTP-T27 | test_t27_revoke_before_connect、test_t27_connect_then_revoke_before_first_send：两种门顺序，连接不计 HTTP、撤权后不首写 |
| HTTP-T28 | test_t28_send_return_and_count_are_one_gate_transaction：Event 屏障控制门内 send 与撤权竞争，不能看到部分记账 |
| HTTP-T29 | test_t29_partial_and_wouldblock_count_once、test_t29_zero_and_failed_send_no_retry：暂不可写、正字节、偏移、失败和不重试 |
| HTTP-T30 | test_t30_time_boundary_after_send_preserves_count、test_t30_initial_planning_in_budget、test_t30_audit_gap_after_positive_send_is_unknown_on_recovery：时间、首次规划与审计缺口 |
| HTTP-T31 | test_t31_revoke_idempotence_duplicate_and_late_events、test_late_response_during_read_cannot_upgrade：幂等撤权、终态与迟到数据 |
| HTTP-T32 | test_t32_missing_approval_and_expiration、test_t32_scope_and_version_mismatch、test_t32_material_hash_and_delegation：材料、过期、撤销、范围和委托 |
| HTTP-T33 | test_t33_snapshot_bytes_are_immutable、版本不匹配及撤权测试：读取字节固化，运行期间不热加载权限 |
| HTTP-T34 | test_t34_canary_cannot_rescue_malformed_framing_or_json、test_response_size_bounds_and_content_type：重复长度／JSON 键、坏编码、超长、截断不可误确认 |
| HTTP-T35 | test_t35_5xx_complete_vs_truncated_leak、test_approved_candidate_pass_is_not_carried_to_broken_next_response：完整 5xx 与损坏片段分开，前项结论不传播 |
| 其他 U 回归 | 六项 Good 与三个单缺陷变体、合法访问过度拒绝、404／5xx／空体、原始凭据与恶意参数／响应字段扫描、8／9 边界、重复 ID、审计故障、必要对照与终态 |

以上是设计场景的无网络确定性子集，不能将 HTTP-T27～T35 的真实系统调度／网络部分标为已验收。

## 5. 风险与剩余工作

- 真实 socket、selectors 调度、API 服务、实际代理隔离／重定向／地址变化验证、在途关闭及取消延迟均未实现或验证。MemoryTransport 类型约束不是防御任意同进程代码的沙箱。
- 批准材料真实性依赖可信操作者；程序验证引用字节、有效期与范围的一致性，不鉴定批准人身份。真实材料和教师目录尚未登记，宿主目录权限及外部撤销消息到本地入口的操作流程仍须落实。
- 本轮只接受版本化六项候选，scope_digest 采用精确匹配；扩大端点、参数、身份或支持宽泛许可自动求交须另审，不能自行扩权。
- 解析器限定单 Content-Length、JSON、无压缩／chunked。读入内存有界；整 run 容量、停止元数据预留、真实磁盘空间与延迟实验尚未完成，不能将单元测试字节参数当正式上限。
- 授权材料和凭据不进入 Evidence；响应只记录判定码，不保存原始内容。当前模拟报告不能替代未来可独立复核的真实响应片段与断言证据。
- 网络与磁盘不可能在本设计中原子提交；前缀分析只说明模拟动作确认／未知，不执行恢复重试，不证明进程崩溃时真实请求数量。
- 新旧状态机有分别维护的规则实现；后续真实集成前要再次核对同一 RC2 边界，不能仅凭原离线测试通过推断新入口正确。

## 6. Git 与停止条件

四份 HTTP 设计文档已在此前 74ed7b1 跟踪；本轮更新其状态／承接段并把历史审核报告纳入跟踪。源码、测试、报告与 README 的具体行数以最终暂存 diff 为准；没有变更 RC2、稳定需求 ID、CI 或原 Evidence。当前工程只完成无网络阶段，尚未获得运行 HTTP 测试授权或功能验收。

下一阶段应先由负责人审核本轮代码，再落实真实目标授权与教师目录、宿主许可登记流程、真实传输边界及集成验收。完成后停止，留给负责人在 GitHub Desktop 审核提交。

### 执行期间的并行 Git 变更

最终检查发现外部提交 `73b150d p3 core`，包含 6 个模块、初版 tests/test_http_core.py 与历史 P3_http_design_review.md。该提交不是本助手创建；未回退、重写或覆盖。最后观察本地 main 与缓存 origin/main 均在 73b150d（0/0），不把它误报为本助手推送成功。该提交之后本轮增加的审计前缀分析、规划／登记竞争修正、后续测试及文档仍需负责人审核提交。

静态检查：本轮起始已有文件中，除明确更新的 README 与四份设计／契约／验收文档外，其余 43 个文件字节哈希一致；包括全部原 Evidence、原核心、49 项测试与 CI。文档链接有效，新模块 AST 未发现网络或子进程导入。当前新增 54 项测试加原 49 项共 103 项通过。
