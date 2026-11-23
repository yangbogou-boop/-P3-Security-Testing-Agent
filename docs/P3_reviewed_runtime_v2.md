# P3 V2 契约驱动离线运行（Reviewed Offline Run）

更新：2026-11-23。基线 `9c59064bb6a9455d52766a485184d7ab6765da76`。本页说明第二批新增的 V2 离线运行框架；它**不改变** V1 `SimulationRun`、LiveRun、旧 `HttpConfig`、旧六项候选、旧授权语义与旧 `scope_digest`。

本框架只在内存中运行：无监听、无 socket、无外部 HTTP 客户端、无大模型接入。真实网络请求与网络延迟一律标记为 `NOT_MEASURED`，OS 未派发证明仍为 `UNAVAILABLE`。

## 1. 模块

| 模块 | 职责 |
|---|---|
| [reviewed_fixture.py](../src/p3_core/http/reviewed_fixture.py) | `FixturePort` 协议、规范化夹具内容摘要 |
| [catalog_fixture.py](../src/p3_core/http/catalog_fixture.py) | 两套独立合成业务：文档（documents）、目录（directories） |
| [reviewed_snapshot.py](../src/p3_core/http/reviewed_snapshot.py) | 不可变私有审核快照 `ReviewedRunSnapshot` 与宿主侧八项核验 |
| [reviewed_protocol.py](../src/p3_core/http/reviewed_protocol.py) | 契约驱动 GET 构造、关联校验、封闭结构判定、证据投影 |
| [reviewed_runtime.py](../src/p3_core/http/reviewed_runtime.py) | `ReviewedOfflineRun`：门禁、交付账本、状态机、计数 |
| [trusted_host.py](../src/p3_core/trusted_host.py) | `build_reviewed_offline_run(...)`：唯一可信入口 |

复用（只读导入）V1 中与业务无关的构件：`ResponseParser`、`Observation`、`Verdict`、`PreparedRequest`、`BoundedEvidence`、`LocalRegistry`、`ReviewedMaterial`、`strict_json`、`digest`。**不**复用 `build_request`、`evaluate`、`IDENTITIES`、`base_checks()` 授权路径。

`ReviewedRunSnapshot` 采用 `NamedTuple`（无可写槽、无实例 `__dict__`），映射字段为 `MappingProxyType`；运行对象私有持有它，仅通过只读属性暴露。因此 `object.__setattr__` 无法替换授权字段，也无法就地修改映射。

合成夹具的业务数据同样不可变：`_Identity`/`_Resource`/`_ScenarioSpec` 均为 `NamedTuple`，模块级场景定义是不可变元组，每个实例持有自己新建的资源与身份元组，`CatalogFixture` 用 `__slots__` 与写保护阻止普通属性替换；不向调用方泄露可变容器。

快照同时记录两种绑定值：

| 值 | 覆盖 | 计算时机 |
|---|---|---|
| `fixture_content_sha256` | 场景、版本、身份四元组、资源、ACL、标记 | `start()` 与交付前（gate 外） |
| `resource_fingerprint` | 资源 id、owner、marker、成员 ACL（排序元组） | 每次派发前与消费前（无哈希，有界） |

## 2. 状态机

```text
PROPOSED ──授权──▶ AUTHORIZED ──构造──▶ PREPARED ──账本接受──▶ DISPATCH_ACCEPTED
                                                                    │
                                                            消费（一次性）
                                                                    ▼
                                                        DELIVERY_CONSUMED → FIXTURE_STARTED
                                                                    │
                                                          FIXTURE_HANDLED → RESPONSE_OBSERVED
```

`step()` 每次只推进一个阶段（授权 → 准备 → 接受 → 交付 → 完成），因此测试可以在"准备完成、尚未派发"处确定性地插入撤权。

## 3. 派发与撤权线性化

- `_gate` 是唯一线性化点：派发接受与 `revoke()` 在同一互斥锁内，`gate_sequence` 给出唯一全序（`dispatch_seq` / `revoke_seq`）。
- 派发接受 = 在 gate 内把一次性 `_Ticket` 放入容量 1 的交付账本并提交计数。**令牌是调用夹具的唯一凭证**。
- 夹具只在 gate 外、接受之后执行；撤权不需要等待夹具，也不做磁盘 I/O。
- 撤权先赢 ⇒ `_checkpoint_locked()` 失败 ⇒ 无 ticket ⇒ 夹具调用数 0。
- 派发先赢 ⇒ 该次交付完成；若撤权在其间到达，事件记 `reviewed_revoked_during_delivery{dispatch_seq, revoke_seq}`，不重试、不重计。

**绑定复核点**

| 时机 | 检查 | 位置 |
|---|---|---|
| `start()` 前 | 身份/版本/实例/身份记录/资源指纹 + 完整内容摘要 | 不匹配即 `FIXTURE_BINDING_MISMATCH`，运行保持 `READY`，无派发 |
| 每次派发接受前（gate 内） | 身份/版本/实例/身份记录/资源指纹（纯比较，无哈希） | 漂移即 `STOPPED`，不产生新派发 |
| 接受后、消费前（gate 外） | 完整内容摘要 | 失败即中止未消费 Ticket，夹具调用 0 |
| 消费提交时（gate 内） | Ticket 仍为 `ACCEPTED`、未撤权、许可有效、指纹未变 | 与消费在同一线性化边界内完成 |

## 4. 计数

`counts` 保持 V1 四键（评价器与摘要器要求精确键集）：

```text
plan_count, attempt_count, request_count=0, model_request_count
model_request_count == dispatch_accepted_count
```

`reviewed_counts` 另存 14 个计数；不变量：

```text
fixture_handled ≤ fixture_started ≤ delivery_consumed ≤ dispatch_accepted
                ≤ prepared ≤ authorized
authorization_decisions == authorized + denied
prepared + prepare_failed ≤ authorized
dispatch_accepted + dispatch_cancelled ≤ prepared
终态：delivery_consumed + delivery_aborted == dispatch_accepted
```

终态等式由 Ticket 生命周期保证：停止时，仍为 `ACCEPTED` 的交付转 `ABORTED` 且只计一次；已 `CONSUMED` 的交付不会再被中止。

## 5. 拒绝码

`FIXTURE_ID_MISMATCH`、`FIXTURE_VERSION_MISMATCH`、`FIXTURE_DIGEST_MISMATCH`、`FIXTURE_INSTANCE_MISMATCH`、`FIXTURE_CONTRACT_VERSION_MISMATCH`、**`FIXTURE_BINDING_MISMATCH`**、`FIXTURE_PORT_INCOMPLETE`、**`FIXTURE_PORT_NOT_IMPLEMENTED`**、`IDENTITY_MISMATCH`、`MATRIX_MISMATCH`、`RESPONSE_RULE_MISMATCH`、`CANDIDATE_MATRIX_MISMATCH`、`MISSING_CREDENTIAL_BINDING`、`DUPLICATE_CREDENTIAL`、`UNKNOWN_REVIEWED_ENDPOINT`、`PATH_PARAMETER_MISMATCH`、`UNREGISTERED_PARAMETERS`、`ANONYMOUS_CREDENTIAL_FORBIDDEN`、`INVALID_CREDENTIAL`、`PREPARE_ERROR`、`FIXTURE_ERROR`、`AUDIT_ERROR`、`DISPATCH_OVERLAP_REJECTED`、`SINGLE_IO_OWNER_REQUIRED`、`REENTRANT_STEP`、`RUN_NOT_TERMINAL`、**`STATUS_MISMATCH`**、**`INVALID_CORRELATION_TYPE`**、**`INVALID_FIELD_TYPE`**。

判定语义：拒绝响应的 `status` 必须等于契约 `rule.status`；不一致时返回 `INCONCLUSIVE / STATUS_MISMATCH`，不判 PASS、也不判为已确认缺陷。

## 5.1 证据诚实性诊断

报告新增 `evidence_complete`（`audit_gap` 为真时为 `false`）与 `unpersisted_event_kinds`（已发生但事件未持久化的事实类别）。审计写盘失败时不会伪造事件链，也不会把该类报告标为完整；`verify_run` 对 `audit_gap=true` 的报告返回 `INCOMPLETE_OR_INVALID`。

## 5.2 终态资源

终止后 `pending_request_count()` 为 0：未派发的请求字节（含 Bearer）在停止分支与 `finalize()` 中释放。Python 的 `bytes` 不可原地清零，因此这里只承诺"不再被对象持有"，不承诺物理擦除。

## 6. 证据与限制

- 事件写入 `events.jsonl`，Manifest 绑定 `report_sha256` / `events_sha256`；`verify_run` 可校验内部一致性。
- 证据只投影已审核 `evidence_fields`；不保存原始响应字节、错误正文或异常文本。
- 审计写入失败 ⇒ `AUDIT_ERROR` 停止，且不再产生未记录的夹具处理。
- 完整性不等于来源认证；`NO_NETWORK_SIMULATION` 不等于真实安全结论。
- 本框架不构成课程验收、教师批准或真实执行授权。

## 7. 复现

```powershell
$env:PYTHONPATH = 'src'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m unittest tests.test_reviewed_snapshot tests.test_reviewed_protocol tests.test_catalog_fixture tests.test_reviewed_runtime -v
```
