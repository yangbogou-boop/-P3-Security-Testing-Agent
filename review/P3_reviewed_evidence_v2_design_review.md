# P3 V2 独立证据校验与计数修复：设计与评审记录（3B-1）

记录日期：2026-11-23。基线 `3af990de8eaef8319f620fb77d5492e3a4678c24`。范围仅 3B-1：重复取消修复、展示层门控、独立校验器与测试；不含 M1–M13 指标模块，不改 V1 评价规则。

## 1. 前置基线（本轮实测）

```text
branch=main  HEAD=3af990de…  parent=9c59064…  sync=0/0  worktree clean
LEGACY71_RUN=71   FAIL=0 ERR=0 SKIP=0
V2_RUN=88         FAIL=0 ERR=0 SKIP=0
FULL_RUN=510      FAIL=0 ERR=0 SKIP=0
LEGACY_SCOPE_DIGEST=d64e9f9b126d1e8f2728287f97408748ef74baf919b3403e7420b06e81ccb948
```

## 2. 缺陷一：重复取消计数

**现象（修复前实测）**

```text
prepared_count=1  dispatch_cancelled_count=2  distinct_cancelled_slots=1
cancel events=2   check_invariants()=[]
```

**成因**：`_stop_locked()` 取消 PREPARED slot 并 +1；`_accept()` 在同一窗口再次进入时又 +1，各发一条事件。单线程测试不可达，故 88 项测试未覆盖。

**修复**

| 改动 | 位置 | 说明 |
|---|---|---|
| 新增 `_cancel_slot_locked(slot, reason)` | `reviewed_runtime.py` | 单一出口；`CANCELLED/ACCEPTED/DONE` 为终态，重复调用返回 False 且不计数 |
| `_stop_locked` 改用它 | 同上 | 取消动作不再重复计数 |
| `_accept` 改用它并删除自建事件 | 同上 | 事件统一由 `_drain_stop_events()` 在锁外补偿 |
| `_cancelled_slots` 记录 `(slot_id, action_id, reason)` | 同上 | 事件保留真实 action 关联与原因 |
| 新增不变量 `accepted + cancelled <= prepared` | `check_invariants` | 已准备槽位至多进入 `accepted` 或 `cancelled` 之一 |

**修复后实测**：`dispatch_cancelled_count=1`、事件 1 条、`check_invariants()=[]`。

**真实计数语义说明**：`dispatch_cancelled_count` 统计"已准备但未派发而被取消的请求数"。由于一个 slot 只能被取消一次，该值等于**去重 slot 数**，不等于取消事件数；校验器按去重语义重放，因此旧证据（计数 2、事件 2、slot 1）会被判 `MISMATCH` 并报 `CANCEL_REPEATED`。

## 3. 缺陷二：展示层误报 COMPLETE

**现象（修复前实测）**：V2 证据经 `verify_run` 为 `VERIFIED`，`offline_summary.summarize()` 返回 `COMPLETE`，而 `reviewed_counts` 从未被核验。

**修复**：`summarize()` 在完成 V1 结构校验后，若 `mode == 'reviewed-offline-simulation'` **或**报告含 `reviewed_counts`，转入 `_reviewed_summary()`：调用独立校验器，按六轴给出 `V2_EVIDENCE_CONSISTENT` / `V2_EVIDENCE_INCONSISTENT` / `INSUFFICIENT_EVIDENCE` / `V2_UNVERIFIED`；`approval_verified` 与 `source_authenticated` 保持 false。

用 `or 'reviewed_counts' in report` 作为第二判据，是为了防止把 V2 报告的 `mode` 改成 V1 值来绕过门控（该情形会被校验器判 `NOT_A_REVIEWED_V2_RUN`）。

**V1 兼容**：V1 记录的代码路径未改变，测试逐项通过，且 V1 摘要不含 `reviewed_evidence` 字段。

## 4. 独立校验器

模块：`src/p3_core/http/reviewed_evidence.py`（只读，约 430 行）。

**信任边界**：只读三份持久化文件；不导入运行器；不调用夹具；不复用运行器计数逻辑；不写证据；不依据报告自称调整标准。

**六轴**：`file_integrity`、`evidence_completeness`、`counter_consistency`、`delivery_association`、`contract_association`、`provenance`，各自独立取值，`consistent` 仅在六轴全部达标时为真。

**计数重放**：14 项独立重算（含 `NOT_RUNNING` 拒绝不计数的特例、取消按 slot 去重、观测需同时具备证据与断言两条事件），并交叉核对四键 `counts` 与每条事件内嵌的计数快照（单调、末值一致）。

**关联**：按 `slot_id` / `action_id` / `dispatch_seq` 建图，检查授权唯一、准备须先授权、取消唯一、接受须有准备、交付终态唯一、中止后不得再启动夹具、处理须先启动、序列唯一、撤权先于派发、终态无未结交付。

**Fail-Closed**：缺文件、哈希不符、序列断号、`audit_gap`、`evidence_complete=false`、`unpersisted_event_kinds` 非空、未知事件类型或字段集不符，一律降级为不完整，绝不输出总体通过。

## 5. 无法从证据证明的事项（如实登记）

| 项 | 缺失证据 | 处理 |
|---|---|---|
| 审核预算 `max_checks` / `budget_version` | 报告未持久化 | `UNPERSISTED_BUDGET`，不推定 |
| 三个摘要的真实性（`contract_digest`/`scope_digest`/`fixture_content_sha256`） | 无事件绑定 | 仅做格式校验，列入 `unverifiable`；篡改成另一个合法 64 位十六进制**不可检测** |
| 已审核候选全集 | 报告只有未执行列表 | 由 `checks ∪ unperformed` 推导，属间接证据 |
| 本地耗时 | 事件无时间戳 | 不提供数值 |
| 审核/执行许可 | 不在证据内 | 三个 verified 标志恒 false |
| T3 进程内任意代码 | 超出边界 | 仅能发现持久化字节中的矛盾 |

**最小补证建议（留待下一批审批，本批不实施）**：在 `reviewed_started` 事件中同时写入 `contract_digest`、`scope_digest`、`fixture_content_sha256` 与 `budget`（`version`/`max_checks`/`logical_timeout_seconds`/`concurrency`），即可把上述前两项从 `unverifiable` 提升为可校验；这会改变事件字段集，需单独评审与兼容性说明。

## 6. 3A 文档更正

### 6.1 硬编码分类统计

3A 表格共 28 项，但文末统计写成 "H1 = 7"，与逐条计数不符。逐条复核后更正为：

| 分类 | 条数 | 条目 |
|---|---|---|
| H1（需消除的业务硬编码） | **10** | HC-04～HC-12、HC-28 |
| H2（应保持的安全上限） | **5** | HC-18、HC-19、HC-21、HC-24、HC-25 |
| H3（必须保留的历史评测基准） | **8** | HC-01～HC-03、HC-13～HC-17 |
| H4（可契约化但需独立审核） | **3** | HC-20、HC-22、HC-26 |
| H5（证据不足暂不决定） | **2** | HC-23、HC-27 |
| 合计 | **28** | — |

### 6.2 覆盖率 M1 设计缺陷

3A 的 M1 定义 `|R| / |R|`（分子分母都取自报告的候选集合），实际恒为 100%，不构成独立验证。

**更正**：M1 的**分母必须是独立审核的候选全集**（来自审核契约或审核快照），而不是报告自述的候选集合。若只能拿到报告，则 M1 必须返回 `NOT_CHECKABLE` 并声明"未独立验证候选覆盖"。该更正留待 3B-2 实现；本批校验器已在 `unverifiable` 中登记"reviewed candidate universe"。

### 6.3 预算不可核验

3A 已指出报告缺预算字段，本批校验器显式返回 `UNPERSISTED_BUDGET`，并确认：**不得因为候选数量是 3 或 4 就推定 `max_checks` 也是 3 或 4**。

## 7. 测试与结果（本轮实测）

| 文件 | 项数 | 变更 |
|---|---|---|
| `tests/test_reviewed_evidence.py` | 31 | 新增 |
| `tests/test_reviewed_runtime.py` | 40 | +6（取消幂等与不变量） |
| `tests/test_offline_summary.py` | 12 | +3（V2 门控、V1 不变） |

覆盖：合法 S1/S2、三种停止形态、篡改 `reviewed_counts`、篡改事件计数、删除接受事件、重复消费、重复取消、单 slot 双取消、接受无终态、中止后启动夹具、无启动即处理、错误 `dispatch_seq`、撤权顺序冲突、未知事件类型、哈希不符、`audit_gap`、未持久化事件、序列断号、摘要篡改（声明不可校验）、非 V2 报告、缺失文件、展示层三种状态、V1 展示不变。

## 8. 残余风险

| 风险 | 级别 | 说明 |
|---|---|---|
| 摘要未绑定事件 | 中 | 篡改成另一个合法摘要在证据层不可检测（本批已声明） |
| 预算未持久化 | 中 | 无法核验是否超审核预算 |
| 事件无时间戳 | 低 | 无耗时指标 |
| T3 进程内任意代码 | 高（已知） | 校验器只能发现持久化字节中的矛盾 |
| 门禁与校验各自实现 | 中 | 双份逻辑存在漂移风险；以 `COUNTERS == COUNTER_KEYS` 测试守护计数名 |

## 9. 未做事项

- 未开发 M1–M13 指标模块（3B-2）。
- 未修改 `evaluator.py`、`experiments.py`、`reviewed_contract.py`、契约授权范围与 Fixed 策略。
- 未新增事件字段（补证建议留待审批）。
- 未改 ADR-005、未关闭 GAP-032、未运行真实 HTTP。

## 10. 第二轮定向整改（MAJOR-1～4）

第一轮提交前审核用四个探针证明校验器存在漏检，本节记录整改。

| ID | 整改前实测 | 整改后实测 | 改动 |
|---|---|---|---|
| MAJOR-1 顺序 | 把 `fixture_started` 移到 `delivery_consumed` 前（重编号+重签）→ `consistent=True` | `violations=['FIXTURE_STARTED_BEFORE_CONSUMED','DELIVERY_AFTER_FIXTURE_STARTED']` | `_association` 增加消费→启动→完成顺序与重复检查 |
| MAJOR-2 槽位 | 把 `dispatch_accepted.slot_id` 换成另一 slot → `consistent=True` | `violations=['ACCEPT_SLOT_MISMATCH','SLOT_ACCEPTED_TWICE']` | 接受事件必须与同 action 的准备 slot 一致，并禁止同 slot 二次接受 |
| MAJOR-3 撤权 | 清空 `report.revoke_sequence` → `consistent=True`（顺序检查被跳过） | `violations=['REVOKE_SEQUENCE_MISSING']` | 新增 `_revoke()`：事件值唯一、与报告相等、派发不得晚于该序列 |
| MAJOR-4 展示 | 改 `mode` 并删 `reviewed_counts`（重签）→ `COMPLETE` | `INSUFFICIENT_EVIDENCE` | `_looks_reviewed()` 按结构分类：V2 字段、`reviewed_*` 事件、`dispatch_seq` 行 |

**事件计数跃迁**：按运行器真实行为建立 `COUNTER_TRANSITIONS`（`proposal_registered→plan_count+1`、`authorization→attempt_count+1`、`dispatch_accepted→model_request_count+1`，其余事件不得改变任何计数），首条事件须全零、末条须等于报告 `counts`。审计缺口存在时降级为单调性检查并登记 unverifiable。

**合法路径保护**：准备后、派发前撤权不会产生带 `revoke_seq` 的交付事件，此时报告值不可独立证明，登记 `revoke sequence binding` 而不判为伪造；预检拒绝型运行没有 `reviewed_started`，按 fail-closed 记 `NOT_CHECKABLE`。

**MINOR**：恢复 `offline_summary.py` 原有 UTF-8 BOM；补齐函数间空行；独立性表述限定为"不依赖运行器及夹具执行逻辑"；删除未使用局部变量；文档补充预检拒绝的 fail-closed 说明；保留"候选全集未独立证明、不据此计算覆盖率"的限制。

**测试**：证据测试 31→42（新增 11 项：顺序 4、撤权 4、计数跃迁 3），摘要测试 12→13（双字段绕过 1）。
