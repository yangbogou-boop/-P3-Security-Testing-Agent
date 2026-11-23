# P3 V2 离线运行第二批设计评审与整改记录

记录日期：2026-11-23。基线 `9c59064bb6a9455d52766a485184d7ab6765da76`。范围仅第二批 V2 离线运行框架及其提交前整改；未修改 V1 与 LiveRun，未运行真实 HTTP，未接入大模型。

## 1. 负责人四项决定的落实

| 决定 | 落实 | 证据 |
|---|---|---|
| C1 先授权、后准备 | `AUTHORIZED → PREPARED`；被拒候选不构造请求 | `test_unknown_id_is_denied_without_dispatch` |
| C2 有条件批准 gate 内线性化 + gate 外夹具 | 派发接受在 gate 内提交账本与计数；夹具在 gate 外、接受之后执行 | `test_revoke_after_prepare_before_dispatch`、`test_revoke_during_delivery_is_recorded_in_order` |
| C3 有条件批准独立运行类 | `ReviewedOfflineRun` 不继承 `SimulationRun`，不 import `machine`/`live`/`transport` | `test_two_scenarios_share_one_run_interface` |
| C4 旧基线 71 项、旧 `scope_digest` 重测 | 已实测：71 项通过；`d64e9f9b…b948` 复算一致 | 本轮回归记录 |

## 2. 提交前独立审查发现与整改

独立审查给出 **C 类（存在安全阻断）** 结论，本轮按最小范围整改。

### 2.1 已整改

| ID | 问题 | 整改 | 验证 |
|---|---|---|---|
| BLOCKER-1 | 派发已接受但未消费时，撤权/过期/审计失败使运行停止，Ticket 既未消费也未中止，终态计数违反 `consumed+aborted==accepted` | `_checkpoint_locked` 停止分支调用 `_abort_ticket_locked()`：仅当 Ticket 状态为 `ACCEPTED` 时转 `ABORTED`、计数一次、队列待发事件；`_deliver` 同路径改为幂等调用，不再重复计数 | `test_revoke_between_accept_and_consume_aborts_ticket`、`test_accept_event_failure_aborts_ticket_safely`、`test_licence_expiry_between_accept_and_consume_aborts_ticket`、`test_terminal_delivery_accounting_invariant`、`test_aborted_ticket_cannot_be_consumed`、`test_consumed_ticket_is_not_aborted_again` |
| MAJOR-1 | DENY 判定只要求 `status ∈ {401,403}`，未比较契约声明的 `rule.status`，错误状态码可被判 PASS | `evaluate_v2` 的 DENY 分支在 `status != rule.status` 时返回 `INCONCLUSIVE / STATUS_MISMATCH`；ALLOW 分支同样以 `status == rule.status` 为通过前提 | `test_deny_declared_401_observed_403_is_not_pass`、`test_deny_declared_403_observed_401_is_not_pass` |
| MAJOR-2 | 运行时未复核实际夹具与快照的绑定，可对不一致夹具派发 | `start()` 前 `_verify_fixture_binding(full=True)`（含内容摘要）不匹配即抛 `FIXTURE_BINDING_MISMATCH`；每次接受派发前在 gate 内做**只含字符串比较**的 `_binding_unchanged()`（不计算摘要），漂移即停止且不派发 | `test_wrong_fixture_at_start_rejected`、`test_binding_change_before_dispatch_rejected` |
| MAJOR-3 | `frozen` 数据类仍可被 `object.__setattr__` 改写 | `ReviewedRunSnapshot` 改为 `NamedTuple`（无 `__dict__`、无可写槽），映射字段仍为 `MappingProxyType`；`run.snapshot` 只暴露该不可变对象 | `test_object_setattr_cannot_change_authorisation_fields`、`test_snapshot_mappings_cannot_be_mutated_in_place` |
| m-1 | 计数先于事件，审计失败时计数与事件不一致且无记录 | `_emit` 在失败（含早期 `audit_gap` 短路）时记入 `unpersisted_event_kinds`；报告新增 `evidence_complete` 与 `unpersisted_event_kinds` | `test_audit_failure_has_no_fabricated_persisted_events` |
| m-2 | 停止后仍持有已构造请求（含 Bearer） | 停止分支与 `finalize()` 清空 `_requests`；新增只读 `pending_request_count()` 便于断言 | `test_terminal_run_drops_request_references` |
| m-3 | `correlate_v2` 用 `str()` 强制转换字段值 | 严格要求信封三字段与 `fields` 的键值均为 `str`，否则 `INVALID_CORRELATION_TYPE` / `INVALID_FIELD_TYPE` | `test_correlation_rejects_non_string_field_values` |
| m-4 | `_require_port` 只查可调用性，抽象桩可逃逸为 `NotImplementedError` | 若方法仍是 `FixturePort` 基类实现则 `FIXTURE_PORT_NOT_IMPLEMENTED` | `test_port_incomplete_rejected` 及既有快照测试 |
| m-5 | 本文档曾声称 Path C 已通过 | 已按实测更正（见 §2.2） | 本文件 |

### 2.2 更正说明

原记录称"Path C 派发与审计边界通过，已接受未消费交付有 `delivery_aborted` 显式状态"。该结论在整改前**不成立**：中止逻辑只存在于 `_deliver` 内，而 `_deliver` 在停止后不会被进入。现整改后该结论成立，并新增 6 项针对性测试。原 `test_audit_failure_blocks_new_fixture_work` 只覆盖"审计失败发生在准备阶段"，不覆盖"接受之后"，故不能作为该结论的证据。

### 2.3 提交前核验发现的夹具漂移问题（F1–F5）

在提交前核验中又发现一个阻断项：**夹具业务数据可变，且能绕过派发前绑定检查**。

**根因**

| 根因 | 位置（整改前） |
|---|---|
| 场景定义是模块级可变 dict，实例直接持有其引用 | `_SCENARIOS` dict；`self._spec = spec` |
| 记录类型为 `@dataclass(frozen=True)`，保留了实例 `__dict__`，`object.__setattr__` 可改写 | `_Identity`、`_Resource` |
| 资源容器是可变 dict，值与模块级配置共享同一对象 | `self._resources = {…}` |
| 派发前检查只比较身份/版本/实例，**不包含资源与 ACL 内容** | `_binding_unchanged()` |

**实测后果（整改前）**

```text
ACL 扩权：_binding_unchanged()=True 后继续派发，handler 使用未审核 ACL
ACL 收权：ALLOW 候选得到 FAIL / CONFIRMED_OVERDENIAL（假"已确认"结论）
跨实例：一次 object.__setattr__ 污染后续实例，后者 build_snapshot 报 MATRIX_MISMATCH
报告仍写快照的 fixture_content_sha256（15f7b360），实际内容已变为 3b03b801
```

**整改（F1–F5）**

| 项 | 改动 | 说明 |
|---|---|---|
| F1 | `_Identity`/`_Resource`/`_ScenarioSpec` 改为 `NamedTuple`；`_SCENARIOS` 改为**不可变元组**；`CatalogFixture` 加 `__slots__` 与写保护 `__setattr__`；`_resources`/`_identities` 为每实例新建的元组；线性查找替代 dict | 数据与容器递归不可变；无共享可变别名；普通属性无法替换数据引用 |
| F2 | 快照新增 `resource_fingerprint`（`((resource_id, owner_id, marker, members), …)` 排序元组），由**夹具实际数据**生成，纯比较、无哈希 | 覆盖资源所有权、成员 ACL、标记等影响权限与响应的字段 |
| F3 | `_binding_unchanged()` 加入指纹比较；`_deliver()` 在 gate 外做完整摘要复核，进入 gate 后再次确认 Ticket 仍为 `ACCEPTED`、未撤权、许可有效，并在同一线性化边界内提交消费 | 检查与使用之间不留"已接受即放行"的窗口；失败只中止未消费交付 |
| F4 | 新增 17 项测试（不可变性 10、指纹 2、交付边界 5） | 复现探针 B/C/D 的整改后行为 |
| F5 | 更新本文与运行文档 | 区分已解决与仍存在的风险 |

**指纹与内容摘要的边界**

| 机制 | 覆盖 | 用途 | 成本 |
|---|---|---|---|
| `fixture_content_sha256` | 场景、版本、契约版本、身份四元组（含 user_id/role/credential_ref）、资源、ACL、标记 | 审核绑定（快照与夹具内容一致） | SHA-256，仅在 `start()` 与交付前（gate 外）计算 |
| `resource_fingerprint` | 资源 id、owner、marker、成员 ACL | 每次派发前与消费前的**有界**绑定比较 | 元组比较，无哈希，资源数有上界（当前 2） |

两者都来自夹具数据，均不从契约 `response_rules` 反向构造；`contract_digest` 与 `scope_digest` 算法未变。

**核心结论**：不可变性是主要保证；摘要/指纹复核是第二层。哈希无法消除"检查后仍被改写"的竞争，因此不宣称抵御任意恶意同进程代码（T3 仍为后续独立事项）。

**探针整改前后对比**

| 探针 | 整改前 | 整改后 |
|---|---|---|
| B ACL 扩权 | `_binding_unchanged()=True`，继续派发未审核数据 | 普通赋值与 `object.__setattr__` 均 `AttributeError`；摘要不变；DENY 候选仍为 PASS/REFUSAL_WITH_CONTROL |
| C ACL 收权 | 产出假的 `FAIL / CONFIRMED_OVERDENIAL` | 修改被拒；ALLOW 候选 PASS/AUTHORIZED_CONTENT；报告摘要与实际一致 |
| D 跨实例污染 | 后续实例继承被改数据，`build_snapshot` 失败 | 记录不可改；新实例数据、摘要均与原始一致 |
| T3 替换数据引用 | 未被发现 | `_binding_unchanged()=False` → `STOPPED/FIXTURE_BINDING_MISMATCH`，`accepted=0`，夹具 0 |

## 3. 四项前置一致性检查（整改后）

| 检查 | 结论 | 依据 |
|---|---|---|
| A 夹具预检不调用待测入口 | 通过 | 宿主用 `reference_expectation()` 从声明性数据派生期望；`handle()` 不参与审核（`test_snapshot_never_uses_request_pipeline`） |
| B 响应格式一致（仅 200/401/403） | 通过 | 未扩展 404；成功/拒绝共用封闭信封；状态码现与契约声明严格比对 |
| C 派发与审计边界 | 通过（整改后） | gate 内只提交内存状态与账本；证据 I/O 全在 gate 外；未消费交付在停止时转 `ABORTED`；审计失败时显式登记未持久化事实 |
| D 计数与撤权异常路径 | 通过（整改后） | 运行期与终态不变量分离；撤权顺序取自 `gate_sequence`；9 条异常路径有对应用例 |

## 4. 与 2A 设计的差异（均已评审接受）

1. **单阶段 step**：每次 `step()` 只推进一个阶段，使"准备后、派发前撤权"可在无测试钩子的情况下确定性构造。
2. **`credential_ref` 使用 `fixture/...` 命名空间**：第一批 `parse_contract` 对该字段有固定前缀校验，本批不修改解析规则。
3. **凭据绑定为"所需 ⊆ 提供"**：夹具可能声明候选未使用的身份；运行期只要求候选所需凭据齐备且值唯一。
4. **`revoked_during_delivery` 在夹具完成后记录**：撤权可能在夹具执行期间到达，事件须在 `fixture_handled` 之后发出以反映真实顺序。
5. **停止时统一结算**：已准备未接受项记 `dispatch_cancelled`，已接受未消费项记 `delivery_aborted`，事件在锁外补发。

## 5. 未修改项（兼容性）

`machine.py`、`contract.py`、`protocol.py`、`audit.py`、`authorization.py`、`transport.py`、`live.py`、`mock_api/*`、`reviewed_contract.py`、`experiments.py`、`evaluator.py`、`offline_summary.py`、`delivery.py` 均未改动。`trusted_host.py` 仅追加 `build_reviewed_offline_run`，`OfflineHost` 与 `main()` 不变。V1 `protocol.evaluate()` 不接收任何 V2 数据。

## 6. 残余风险

| 风险 | 级别 | 说明 |
|---|---|---|
| 进程内任意代码（T3） | 高（已知，不声称隔离） | 夹具数据已不可变、派发与消费前均有绑定复核，可发现**经受支持接口**的替换与漂移；但进程内代码可直接改写运行对象或证据，真正隔离需进程边界 |
| 夹具摘要排除凭据密文 | 中 | 摘要无法检测凭据替换；由实例绑定、registry scope、运行期绑定核对共同承担 |
| `counts` 键集固定 | 中 | 评价器与摘要器要求精确四键，V2 计数另置 `reviewed_counts` |
| `verify_run` 不校验 `reviewed_counts` | 中 | 内部完整性通过不等于计数自洽；V2 侧以 `check_invariants()` 与 `evidence_complete` 补充，建议后续增加专用校验器 |
| 响应对 ACL 无独立复核 | 低 | `handle` 复用 `reference_expectation`；ACL 错误由独立硬编码的契约期望捕获 |
| `FixturePort` 未含 `resource_records` | 低 | 本批白名单未包含 `reviewed_fixture.py`，该要求由 `_require_port` 的强制列表承担；后续批次应回填 ABC |
| 无 CLI 入口 | 低 | 可复核性依赖测试与宿主函数，杜绝误用为真实运行 |

**已解决（本轮）**：夹具资源/ACL 可变（F1）、派发前检查不覆盖资源内容（F2/F3）、跨实例共享可变对象（F1）、接受后交付前无复核（F3）。

## 7. 未完成事项

- GAP-032 仍为**部分整改**，未关闭；本批只新增受控 V2 路径，未去除 V1 硬编码。
- 未接 CLI；无真实执行、无课程验收、无教师批准。
- 未修改 ADR-005；未重跑历史 36 次实验。
- 本轮未启动 2C 或第三批。
