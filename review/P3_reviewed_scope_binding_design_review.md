# P3 V2 审核预算与候选全集绑定：设计与评审记录（3B-2A）

记录日期：2026-11-23。基线 `103a9ed36a696a9d686ed998a6fa9fd3472fea2c`。范围仅 3B-2A：把**已审核的运行范围**（预算、候选全集、摘要集）持久化并与运行开始事件绑定；不含 M1–M13 指标模块，不改动授权与安全门禁语义。

## 1. 起点与缺口

3B-1 后，独立校验器可以重放 14 项计数、核对交付链与撤权序列，但无法回答两个问题：

1. 这次运行是否超出了**审核允许的预算**？（报告没有 `max_checks`/`budget_version`）
2. 覆盖率的分母是什么？（报告只有 `unperformed_approved_candidates`，不是已审核全集）

同时，`contract_digest`/`scope_digest`/`fixture_content_sha256` 只存在于报告中，没有任何事件与之绑定，因此单字段篡改（重算报告哈希后）不可检测。

## 2. 方案选择

| | 方案A：扩展 `reviewed_started` | 方案B：新增 `reviewed_scope_binding` |
|---|---|---|
| 事件语义 | 与"已开始"混杂 | 单一职责：绑定范围 |
| 旧证据兼容 | 需同时支持两种字段集，`reviewed_started` 的精确字段校验要分叉 | 旧证据没有新事件，天然不受影响 |
| 可扩展性 | 每加一个范围字段都改旧事件 | 新事件独立演进，可随版本替换 |
| 改动量 | 中等（改事件 + 校验器分叉） | 小（新增一次 emit + 一个分支） |

**选择方案B**。理由：事件语义单一、旧证据零改动、字段集校验无需分叉，且可以让"范围绑定"随 `evidence_version` 独立演进。

## 3. 证据结构

运行开始时（`start()` 内、任何提案之前）发出：

```text
reviewed_started          {snapshot_id, contract_id, fixture_instance_id}
reviewed_scope_binding    {evidence_version, snapshot_id, contract_digest,
                           scope_digest, fixture_content_sha256,
                           fixture_instance_id, budget_version, max_checks,
                           logical_timeout_seconds, concurrency, candidates[]}
```

报告同时写入 `evidence_version` 与 `reviewed_scope`（同样的 11 个字段）。于是校验器可以做三方比较：

```text
报告顶层字段  ←→  report.reviewed_scope  ←→  reviewed_scope_binding 事件
```

任何一方被单独修改都会触发 `SCOPE_<FIELD>_MISMATCH` 或 `SCOPE_FIELD_MISMATCH`。

**来源与边界**：全部取值来自 `ReviewedRunSnapshot`（运行器私有、不可变），没有任何运行参数入口可以写入；`candidates` 上限 64（与契约 `MAX_ROWS` 一致），排序去重，单个 ID ≤64 字符；不包含凭据、令牌或响应数据。

## 4. 版本与兼容

`evidence_version = 'p3-reviewed-evidence-v2'`。

| 证据 | 行为 |
|---|---|
| 3B-1（无 `reviewed_scope`、无事件、无版本字段） | `scope_binding_consistency = NOT_CHECKABLE`，`scope_notes=['SCOPE_BINDING_ABSENT']`，六轴判定与之前完全一致；`unverifiable` 明确列出"审核预算"和"已审核候选全集" |
| 3B-2A | 必须三方一致；否则 `MISMATCH`，整体 `consistent=false` |
| 混合（有版本字段但无事件/块） | `SCOPE_BINDING_MISSING` / `SCOPE_BLOCK_MISSING`，`MISMATCH` |

旧证据不会因为缺少新字段而被改判为失败，也不会被声称"通过了预算与候选全集核验"。

## 5. 预算语义

三层必须区分：

| 层 | 含义 | 载体 |
|---|---|---|
| 审核允许的预算 | 契约声明的 `max_checks`/`timeout`/`concurrency`/`version` | 快照 → 范围事件 |
| 运行实际消耗 | 已提交 slot 数、`authorization_decisions`、`dispatch_accepted` | 计数与事件 |
| 评价统计分母 | 已审核候选全集 | `reviewed_scope.candidates` |

校验规则：`max_checks ∈ [1,64]`、`timeout ∈ (0,3600]`、`concurrency == 1`、`len(checks) ≤ max_checks`。**预算与候选数量相互独立**：4 项候选配 2、4、8 都合法；不得由候选数推断预算，也不得把全局安全上限（64/3600）当作契约预算。

## 6. 候选全集语义

`reviewed_scope.candidates` 是**已审核候选全集**，与以下集合严格区分：

- 已提交的有效审核候选：报告行中 `check_id` 非空且 ∈ 全集；
- 已准备/已接受/已处理/已形成结论：分别由 `reviewed_prepared`、`dispatch_accepted`、`assertion` 事件刻画；
- 未完成候选：不能用 `unperformed_approved_candidates` 当作"未提交"，它只表示"未处理"。

校验器要求每个非空 `check_id` 都属于全集，否则 `CANDIDATE_NOT_REVIEWED`；未知候选在运行器中仍然判 `DENY`，不会因为出现在报告行里被当成已审核。

## 7. 信任边界

报告与事件"相互一致"只证明**持久化材料的内部一致性**。若攻击者能同时改写三份文件并重算摘要，且没有独立可信的审核材料，仍无法证明来源真实。因此：

- `approval_verified`、`source_authenticated`、`runtime_authorisation_verified` 继续恒为 `false`；
- `unverifiable` 明确保留"摘要的外部权威性""外部审核与执行许可"两项；
- 本批不声称已独立认证外部审核、已证明授权材料真实或已证明真实 API 获得执行许可。

## 8. 顺带修复

3B-1 校验器要求 `reviewed_proposal_rejected` 事件的字段集精确等于 `{reason}`，而运行器在 `DUPLICATE_PROPOSAL`/`BUDGET_EXHAUSTED` 分支还会带 `candidate`。结果是任何发生预算拒绝的合法运行都会被判 `INVALID_EVENT_FIELDS`（fail-closed，不会误通过，但会把合法证据判为不完整）。本轮新增 `EVENT_OPTIONAL`，允许该字段出现或缺失。

## 9. 测试

已有 3B-2A 工作区新增 29 项（运行 8、校验 21），覆盖：

- S1/S2 正常范围绑定、事件先于任何提案；
- 预算 <、=、> 候选数量；预算被行数超出；
- 报告/事件侧 `max_checks`、`budget_version` 篡改；
- 候选被删除、添加未审核项、重复、乱序、行越界；
- 摘要单字段篡改被检出、三方同时改写仍标注不可验证；
- 缺事件、重复事件、版本不一致、旧格式证据 `NOT_CHECKABLE`；
- 审计缺口不得因范围字段而通过；
- 两套契约共用校验器且无业务名分支；
- 修改预算后旧审核范围绑定失效（构造层面）。

## 10. 残余限制

| 项 | 说明 |
|---|---|
| 外部审核真实性 | 无独立材料，仍不可验证 |
| 摘要权威性 | 仅内部三方一致 |
| 真实网络 | 仍未执行，`real_network_requests`/`network_latency` 恒为 `NOT_MEASURED` |
| T3 | 进程内任意代码未隔离 |
| 指标 | M1–M13 留待 3B-2B |

## 11. 续行评审

实现的最终字段及兼容性以[运行范围绑定](../docs/P3_reviewed_evidence_v2.md#51-运行范围绑定3b-2a)为准。续行复核保留独立事件方案，补齐契约和夹具的 ID、版本，增加 Manifest 版本和本地范围散列，并严格核验事件顺序、字段类型和槽位证据。若范围事件写入失败，继续沿用审计失败停止路径。提案与步进在范围事件持久化后进入已有流程，授权、预算、撤权和交付门禁沿用原实现。

候选生命周期从事件重建，与报告的未完成集合核对；审计缺口时保留原有 fail-closed，禁止输出候选重建结论。本地范围散列可发现部分重写，三文件全部重写并重新封存仍属于外部真实性边界。真实网络耗时、正式批准和实际系统级隔离没有由本轮验证。
