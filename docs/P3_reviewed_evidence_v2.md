# P3 V2 独立证据校验（Reviewed Evidence Verifier）

更新：2026-11-23。基线 `3af990de8eaef8319f620fb77d5492e3a4678c24`。本页说明第三批 3B-1 新增的只读校验器、展示层门控与计数修复；不涉及真实 HTTP。

## 1. 为什么需要独立校验

`verify_run()` 只证明三份证据文件**彼此自洽**：报告哈希、事件前缀哈希、运行 ID、四键计数。它**不**核验 V2 的 14 项 `reviewed_counts` 与事件是否对应，也不判断交付是否有终态。

V1 评价器对此 fail-closed：实测三条规则（DENY/BUDGET/REVOKE）对 V2 证据一律返回 `INSUFFICIENT_EVIDENCE`，因为字段集与事件词表不同。因此 V2 证据此前**没有任何独立校验**。

## 2. 校验器

[reviewed_evidence.py](../src/p3_core/http/reviewed_evidence.py) 只读取 `manifest.json` / `report.json` / `events.jsonl`：

- 不导入 `ReviewedOfflineRun`，不调用夹具 `handle`，不执行任何候选检查；
- 不复用运行器的计数计算过程（只复用 `evaluator` 的安全读取与严格 JSON 原语）；
- 不写证据目录，不修改报告，不生成缺失事件。

独立性边界：**不依赖运行器及夹具执行逻辑**。它仍通过 `evaluator` 复用通用文件/JSON 原语，因此间接依赖 `http.audit` 的导入，但不调用其判定。

## 3. 六轴输出

| 轴 | 取值 | 含义 |
|---|---|---|
| `file_integrity` | `VERIFIED` / `INCOMPLETE_OR_INVALID` | 三文件哈希、`events_bytes` 前缀、运行 ID |
| `evidence_completeness` | `COMPLETE` / `INCOMPLETE` | `audit_gap`、`evidence_complete`、`unpersisted_event_kinds`、序列连续、事件字段集 |
| `counter_consistency` | `MATCH` / `MISMATCH` / `NOT_CHECKABLE` | 14 项计数重放 + 四键 `counts` 交叉核对 + 每个事件内嵌计数快照 |
| `delivery_association` | `CONSISTENT` / `VIOLATION` / `NOT_CHECKABLE` | slot/action 图、终态、序列号、撤权顺序 |
| `contract_association` | `CONSISTENT` / `MISMATCH` / `NOT_CHECKABLE` | 报告与 `reviewed_started` 事件的快照/契约/夹具实例一致性 |
| `provenance` | `NO_NETWORK_SIMULATION` / `UNKNOWN` | 来源标记与"未测量"声明 |

`approval_verified`、`source_authenticated`、`runtime_authorisation_verified` **恒为 false**：证据里没有审核材料或执行许可，哈希完整不等于许可真实。

## 4. 计数重放映射

| 计数 | 独立规则 |
|---|---|
| `authorization_decisions` | `reviewed_authorization` 事件数 |
| `authorized_count` / `denied_count` | 按 `decision` 分桶 |
| `proposal_rejected_count` | 拒绝事件数，**排除 `reason='NOT_RUNNING'`**（该分支不加计数） |
| `prepared_count` / `prepare_failed_count` | 对应事件数 |
| `dispatch_accepted_count` | `reviewed_dispatch_accepted` 事件数 |
| `delivery_consumed_count` / `delivery_aborted_count` | 对应事件数 |
| `fixture_started_count` / `fixture_handled_count` / `fixture_failed_count` | 对应事件数 |
| `dispatch_cancelled_count` | **去重后的 slot 数**（同一 slot 只能取消一次） |
| `response_observed_count` | 同时具备 `reviewed_response_evidence` 与 `reviewed_assertion` 的 action 数 |

同时校验 `counts`：`request_count == 0`、`model_request_count == dispatch_accepted_count`、`attempt_count == authorization_decisions`、`plan_count == len(checks)`；并要求每个事件内嵌的四键计数单调不减、末条等于报告计数。

## 5. 关联规则（违反即 `VIOLATION`）

**交付链顺序**（同一 action 必须严格满足）：

```text
dispatch_accepted → delivery_consumed → fixture_started → fixture_handled | fixture_failed
```

违反记：`FIXTURE_STARTED_BEFORE_CONSUMED`、`DELIVERY_AFTER_FIXTURE_STARTED`、`FIXTURE_STARTED_TWICE`、`FIXTURE_FINISHED_TWICE`、`HANDLED_WITHOUT_STARTED`、`FAILED_WITHOUT_STARTED`、`FIXTURE_STARTED_AFTER_ABORT`、`CONSUMED_TWICE`、`ABORTED_TWICE`、`CONSUMED_AND_ABORTED`、`CONSUMED_AFTER_ABORT`、`ABORT_AFTER_CONSUME`。

**槽位与派发绑定**：`ACCEPT_SLOT_MISMATCH`（接受事件的 slot 必须等于该 action 的准备 slot）、`SLOT_ACCEPTED_TWICE`、`ACCEPT_WITHOUT_PREPARED`、`ACTION_PREPARED_TWICE`、`SLOT_PREPARED_TWICE`、`CANCEL_SLOT_MISMATCH`、`CANCEL_REPEATED`、`CANCEL_WITHOUT_PREPARED`、`SLOT_ID_DUPLICATE`、`DISPATCH_SEQ_DUPLICATE`、`DELIVERY_WITHOUT_ACCEPT`、`DELIVERY_SEQ_MISMATCH`、`UNTERMINATED_DELIVERY`、`AUTHORIZATION_*`、`ROW_*`。

**撤权序列**：事件中出现的 `revoke_seq` 必须唯一且与报告 `revoke_sequence` 相等，否则记 `REVOKE_SEQUENCE_CONFLICT`、`REVOKE_SEQUENCE_MISMATCH`、`REVOKE_SEQUENCE_MISSING`；所有 `dispatch_seq` 必须小于该序列，否则 `DISPATCH_AFTER_REVOKE`。`revoked_during_delivery` 的 `revoke_seq` 必须大于被中断的 `dispatch_seq`（gate 线性化，不混同事件序号）。

合法例外：准备后、派发前撤权时没有任何交付事件携带 `revoke_seq`。此时报告值无法独立证明，登记为 `revoke sequence binding`（unverifiable），**不判为伪造**。同理，预检拒绝型运行没有 `reviewed_started`，按 fail-closed 记为 `NOT_CHECKABLE`。

## 5.1 事件计数跃迁表

每个事件都携带当时的四键 `counts` 快照。无审计缺口时按下表逐事件核对增量：

| 事件 | 必须变化 | 其余三项 |
|---|---|---|
| `reviewed_proposal_registered` | `plan_count` +1 | 不变 |
| `reviewed_authorization` | `attempt_count` +1 | 不变 |
| `reviewed_dispatch_accepted` | `model_request_count` +1 | 不变 |
| 其余全部事件（started/preflight/prepared/prepare_failed/cancelled/consumed/aborted/fixture_*/response_*/assertion/control/completion） | 不变 | 不变 |

首条事件必须全零；末条必须等于报告 `counts`。违反记 `EVENT_COUNTS_INITIAL_NONZERO`、`EVENT_COUNT_TRANSITION_MISMATCH`、`EVENT_COUNTS_FINAL_MISMATCH`、`EVENT_COUNTS_NOT_MONOTONE`。

审计失败时（`audit_gap`、`evidence_complete=false` 或 `unpersisted_event_kinds` 非空），已提交的计数可能没有对应事件，精确跃迁**不可判定**：只保留单调性检查，并把 `event counter transitions` 登记为 unverifiable。

## 6. Fail-Closed

```text
缺文件 / 哈希不符 / 序列断号 / audit_gap / evidence_complete=false /
unpersisted_event_kinds 非空 / 未知事件类型 / 字段集不符
  → 该轴 INCOMPLETE 或 INCOMPLETE_OR_INVALID，consistent=false
计数不一致 / 关联违反
  → 对应轴 MISMATCH / VIOLATION，consistent=false
```

校验器不读取运行器的 `check_invariants()` 结果，也不因报告自称 `COMPLETED` 而放行。

## 7. 明确不可证明事项

| 项 | 缺失证据 |
|---|---|
| 审核预算（`max_checks` / `budget_version`） | 报告未持久化 → `UNPERSISTED_BUDGET`；不得由候选数量（3 或 4）推定 |
| `contract_digest`、`scope_digest`、`fixture_content_sha256` 的真实性 | 无事件绑定这些摘要，仅报告哈希防篡改 |
| 已审核候选全集 | 报告只有 `unperformed_approved_candidates`，需与 `checks` 合并推导；本轮不据此计算覆盖率 |
| 撤权序列（准备后、派发前撤权时） | 无交付事件携带 `revoke_seq` → 登记 unverifiable |
| 事件计数精确跃迁（存在审计缺口时） | 计数已提交但事件未落盘 → 只保留单调性检查 |
| 本地耗时 | 事件无时间戳 |
| 审核/执行许可 | 不在证据内 |
| T3 进程内任意代码 | 超出本校验器边界 |

这些项在 `unverifiable` 与 `limitations` 中逐条列出，不写成"已验证"。

## 8. 展示层门控

`offline_summary.summarize()` 先按**结构**判定证据类别，再决定是否进入 V2 分支：

| 判据 | 说明 |
|---|---|
| `mode == 'reviewed-offline-simulation'` | 显式 V2 记录 |
| 报告含 `reviewed_counts` / `resource_fingerprint` / `evidence_complete` / `unpersisted_event_kinds` / `fixture_content_sha256` | V2 专用字段 |
| 任一事件 `kind` 以 `reviewed_` 开头 | V2 事件名空间 |
| 任一行含 `dispatch_seq` | V2 专用行字段 |

任一命中即进入 V2 校验；**只改 `mode`、或同时删除 `reviewed_counts`，都不能降级为 V1**（后者会被判为混合证据，返回 `INSUFFICIENT_EVIDENCE`）。全部不命中才走原 V1 路径。

| 情形 | 状态 |
|---|---|
| 六轴全部通过 | `V2_EVIDENCE_CONSISTENT` |
| 计数/关联不一致 | `V2_EVIDENCE_INCONSISTENT` |
| 文件完整性或证据完整性不足 | `INSUFFICIENT_EVIDENCE` |
| 校验器不可用 | `V2_UNVERIFIED` |

V1 记录路径逐行未变（仍为 `COMPLETE` / `NO_VALID_TESTS` / `SAFETY_STOP` / `INSUFFICIENT_EVIDENCE`），且不产生 `reviewed_evidence` 字段。

`V2_EVIDENCE_CONSISTENT` 只表示"存储的证据内部一致"，不代表 API 安全、审核真实或执行许可有效。

## 9. 取消计数修复

- 取消动作统一走 `_cancel_slot_locked()`：`CANCELLED` / `ACCEPTED` / `DONE` 为终态，重复进入不计数、不产生第二条事件。
- `_accept()` 不再自行发事件，统一由 `_drain_stop_events()` 在锁外补偿。
- `check_invariants()` 新增 `dispatch_accepted_count + dispatch_cancelled_count <= prepared_count`。

## 10. 复现

```powershell
$env:PYTHONPATH = 'src'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m unittest tests.test_reviewed_evidence tests.test_reviewed_runtime tests.test_offline_summary -v
```
