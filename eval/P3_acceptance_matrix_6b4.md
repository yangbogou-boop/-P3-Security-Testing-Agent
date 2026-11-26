# P3 Acceptance Matrix · 6B-4 证据增量

基线 7178dbbb5f3caedca6e7e53cf85a5785d70ecc82。需求、优先级、GWT 逐字取自 [RC2 稳定需求总表](../brief/P3_specification_v1.0-rc2.md)。场景含义见 [GWT](P3_GWT_scenarios.md)，早期资料保留在[原追踪](P3_requirement_traceability.md)。本表将源码、已执行案例、实际执行身份、归档目录和两类人工验收分开。负责人栏为现有项目责任及核查角色，具体分工、签署及教师批准待确认。F2 记录为既有审核；6B-4 未重跑产品测试。无原始结果的场景如实标记，完整测试数量不充作单项证明。

## 证据索引

### Evidence F

**F · F2 历史逐测试记录。** [F2 交付包](https://chatgpt.com/library?file_id=libfile_41409366e0988191b974741848a9d4f6&account_id=personal) 的 logs/full.log 可按本表测试名定位到 ok，另有 logs/metrics.log、logs/new_scope.log、logs/terminal.log 与 scenario-metrics.json。F2 交付补丁对应 711550a 基线的工作区增量，后来正式提交为 7178dbb。第三轮历史独立复跑的同名用例也核对为 ok。包和独立日志分别为 2026-11-25 既有证据；产品测试在 6B-4 标记 NOT_REEXECUTED。[验收历史](../review/P3_reviewed_metrics_v1_acceptance.md)。

### Evidence A

**A · R01 首次。** [执行上下文](../evidence/course_ch03/eval_20261028_01/execution_context.json)、[事件](../evidence/course_ch03/eval_20261028_01/artifacts/run_e2b938e432d044e69427e50f2b1a9aaf/events.jsonl)、[报告](../evidence/course_ch03/eval_20261028_01/artifacts/run_e2b938e432d044e69427e50f2b1a9aaf/report.json)、[Manifest](../evidence/course_ch03/eval_20261028_01/artifacts/run_e2b938e432d044e69427e50f2b1a9aaf/manifest.json)、[原核查](../evidence/course_ch03/eval_20261028_01/verification.json)。原件缺报告摘要；原完整性失败保留。

### Evidence B

**B · R01 整改后。** [上下文](../evidence/course_ch03/eval_20261028_02/execution_context.json)、[执行版本补丁](../evidence/course_ch03/eval_20261028_02/execution_code_diff.patch)、[事件](../evidence/course_ch03/eval_20261028_02/artifacts/run_ce4b0027ae024f05a72d81173c9f05e2/events.jsonl)、[报告](../evidence/course_ch03/eval_20261028_02/artifacts/run_ce4b0027ae024f05a72d81173c9f05e2/report.json)、[Manifest](../evidence/course_ch03/eval_20261028_02/artifacts/run_ce4b0027ae024f05a72d81173c9f05e2/manifest.json)、[原核查](../evidence/course_ch03/eval_20261028_02/verification.json)。客户端 VERIFIED 与合成来源同时成立；不等于真实执行。

### Evidence C

**C · 历史监督。** [原日志移交清单](../evidence/course_ch03/c3c_supervisor_20261022/INVENTORY_SHA256.json)、[监督审核](../review/P3_c3_supervisor_review.md)；最终 258 项的执行内容含工作区增量。

### Evidence D

**D · 历史独立 DENY 判例。** [DENY_K1 输出](../evidence/course_ch03/eval_20261104_evaluator/DENY_K1.json)、[执行上下文](../evidence/course_ch03/eval_20261104_evaluator/context_before.json)。评价执行与产品 R01 是两回事。

### Evidence E

**E · 历史评价器只读 CLI。** [调用与退出](../evidence/course_ch03/eval_20261104_evaluator/case_execution_records.json)、[九次输出与输入目录](../evidence/course_ch03/eval_20261104_evaluator/README.md)。退出 0 表示评价完成，规则本身可为 PASS、FAIL 或证据不足。

### Evidence S

**S · 历史 Fixed/Dynamic。** [108 原件清单](../evidence/course_ch04/strategy_history_36/archive_manifest.json)、[运行目录索引](../evidence/course_ch04/strategy_history_36/README.md)、[事后分析](P3_engineering_experiment.md)、[ADR-005 接受记录](../review/P3_adr005_acceptance_20261116.md)。36 次是 24 COMPLETED、12 STOPPED；逐次执行版本 NOT_FULLY_BOUND。事前实验卡未形成；人工准备及复核耗时未测；每格三次不足以支持统计显著性。ADR-005 仅为内部离线工程接受，REQ-021 仍未正式验收。

### Evidence Q

**Q · 3B-2A 范围切片。** [设计与测试入口](../review/P3_reviewed_scope_binding_design_review.md)、[版本与范围协议](../docs/P3_reviewed_evidence_v2.md)。当时本地接受日志 full 603、范围 40；本轮读取该记录，原运行输出未进入 Git，便携证据以 F 中同组已存日志和场景数据为准。

### Evidence H

**H · 缺口。** [真实 HTTP 清单](P3_http_integration_status.json)为 14 项 PENDING_AUTHORIZATION，无真实执行证明。REQ-022 无真实 LLM 数据或执行材料。教师 A-03/A-05 仍待确认，见[治理](../brief/P3_decision_governance.md)。

## V2 变更承接与证据边界

| 提交 | RC2 承接 | 已实现、自动验证和提交范围 | 人工及课程 |
|---|---|---|---|
| 9c59064 | REQ-001/002/008/009 | 版本化合成契约、域与绑定；契约回归 | 待人工、待教师 |
| 3af990d | REQ-007/010–012/014–018 的离线子场景 | 夹具、门禁、撤权、模拟证据；快照与运行测试 | 待人工、待教师 |
| 103a9ed | REQ-014–017 | 独立证据重放及展示门控，14 项计数；证据回归 | 待人工、待教师 |
| 711550a | REQ-010/015/017，补充 REQ-020 元数据 | 审核范围与预算、候选全集和摘要绑定；范围回归 | 待人工、待教师 |
| 7178dbb | 补充 REQ-014/017/020 的统计解释 | M1–M13、F1/F2 和 22 项指标回归；技术提交前已审核 | 指标定义是内部工程扩展，P1 与正式课程验收另待 |

[运行说明](../docs/P3_reviewed_runtime_v2.md)、[证据说明](../docs/P3_reviewed_evidence_v2.md)、[指标定义](../docs/P3_reviewed_metrics_v1.md)。M7 NOT_CHECKABLE，M10 仅审计状态与缺口、完整率 null，M12 NOT_MEASURED，M13 NOT_APPLICABLE。具体对照候选身份与外部审核来源尚不可独立证明。approval_verified、source_authenticated、runtime_authorisation_verified 仍为 false。GAP-032 保持 PARTIAL。

## 22 项逐条矩阵

| Requirement ID | Requirement | Priority | GWT | Design | Implementation | Verification | Evidence | Execution Version | Archive Version | Verification Scope | Engineering Status | Human Review Status | Course Acceptance | Limitation | Owner |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P3-REQ-001 | 基于接口契约和预期权限矩阵实施黑盒检查；验证必要输入，缺失或矛盾时停止且不发请求。 | MUST | GWT-N01 | [ADR-002](../design/ADR_002_black_box_api_scope.md) | [reviewed_contract.py](../src/p3_core/http/reviewed_contract.py)、[reviewed_snapshot.py](../src/p3_core/http/reviewed_snapshot.py) | [test_preflight_fail_has_no_plan_or_io](../tests/test_http_core.py)、[test_matrix_mismatch_rejected](../tests/test_reviewed_snapshot.py) | [F](#evidence-f) | F2：711550a + 审核补丁（代码字节对应 7178dbb） | F2 ZIP，未入 Git 的日志 | 缺契约／矩阵冲突时离线预检拒绝 | 已实现／自动验证／提交（离线） | 待负责人／适用时 P1 | PENDING_TEACHER_CONFIRMATION | 真实验收及教师契约待定 | P3 负责人（契约与预检） |
| P3-REQ-002 | 仅对经批准的本地隔离模拟 HTTP JSON API 使用模拟凭据和只读操作。 | MUST | GWT-P01、GWT-A02 | [ADR-002](../design/ADR_002_black_box_api_scope.md) | [reviewed_contract.py](../src/p3_core/http/reviewed_contract.py)、[reviewed_protocol.py](../src/p3_core/http/reviewed_protocol.py) | [test_synthetic_permission_cannot_start_live_run](../tests/test_remaining.py)、[test_parameter_domain_enforced](../tests/test_reviewed_protocol.py) | [F](#evidence-f) | F2：711550a + 审核补丁（代码字节对应 7178dbb） | F2 ZIP，未入 Git 的日志 | 合成许可不能开启真实运行，参数域受限 | 已实现／自动验证／提交（离线） | 待负责人／适用时 P1 | PENDING_TEACHER_CONFIRMATION | 真实目标授权与课程范围未取得 | P3 负责人（可信授权） |
| P3-REQ-003 | 确定性 Planner 从批准候选生成有限计划；固定策略的同一输入／配置／版本产生相同计划，动态策略在同一输入及既有结果序列下产生相同选择。 | MUST | GWT-P04、GWT-P05 | [ADR-005](../design/ADR_005_deterministic_strategy_comparison.md) | [strategies.py](../src/p3_core/http/strategies.py)、[experiments.py](../src/p3_core/experiments.py)、[FixedPlanner](../src/p3_core/planner.py) | [test_strategy_repeatable](../tests/test_remaining.py)、[test_fixed_plan_is_deterministic_and_does_not_mutate_config](../tests/test_core.py#L89) | [F](#evidence-f)、[S](#evidence-s) | F2：711550a + 审核补丁（代码字节对应 7178dbb）；NOT_FULLY_BOUND（36 次） | F2 ZIP，未入 Git 的日志；9754048 归档基线；04214d3 路径提交 | FixedPlanner 对同一解析候选集的两次规划相同；合成默认场景下两次动态运行的顺序相同。36 次历史实验另归档 | 已实现／自动验证／提交（离线） | 待负责人／适用时 P1 | PENDING_TEACHER_CONFIRMATION | 上述断言限固定规划单元和一个动态合成场景；36 次历史执行仍 NOT_FULLY_BOUND，伙伴复现未取得 | P3 负责人（策略实验） |
| P3-REQ-004 | 检查受保护端点的未认证访问，以权限矩阵和响应证据判定。 | MUST | GWT-P02、GWT-N02 | [ADR-002](../design/ADR_002_black_box_api_scope.md) | [core.py](../src/p3_core/mock_api/core.py)、[reviewed_protocol.py](../src/p3_core/http/reviewed_protocol.py) | [test_three_defects_both_strategies](../tests/test_remaining.py)、[test_anonymous_request_has_no_authorization_header](../tests/test_reviewed_protocol.py) | [F](#evidence-f)、[S](#evidence-s) | F2：711550a + 审核补丁（代码字节对应 7178dbb）；NOT_FULLY_BOUND（36 次） | F2 ZIP，未入 Git 的日志；9754048 归档基线；04214d3 路径提交 | 旧三类夹具的匿名子例与 V2 匿名投影 | 已实现／自动验证／提交（离线） | 待负责人／适用时 P1 | PENDING_TEACHER_CONFIRMATION | 合成结果不证明真实匿名访问响应 | P3 负责人（夹具与契约） |
| P3-REQ-005 | 检查模拟用户访问他人对象的对象级权限，并关联合法所有者访问对照。 | MUST | GWT-P02、GWT-N02 | [ADR-002](../design/ADR_002_black_box_api_scope.md) | [core.py](../src/p3_core/mock_api/core.py)、[reviewed_protocol.py](../src/p3_core/http/reviewed_protocol.py) | [test_three_defects_both_strategies](../tests/test_remaining.py)、[test_deny_candidate_requires_control_for_pass](../tests/test_reviewed_protocol.py) | [F](#evidence-f)、[S](#evidence-s) | F2：711550a + 审核补丁（代码字节对应 7178dbb）；NOT_FULLY_BOUND（36 次） | F2 ZIP，未入 Git 的日志；9754048 归档基线；04214d3 路径提交 | 旧对象级夹具子例及 V2 对照门槛 | 已实现／自动验证／提交（离线） | 待负责人／适用时 P1 | PENDING_TEACHER_CONFIRMATION | V2 证据不独立证明具体对照候选身份 | P3 负责人（夹具与契约） |
| P3-REQ-006 | 检查低权限角色访问角色专属端点，并关联合法角色访问对照。 | MUST | GWT-P02、GWT-N02 | [ADR-002](../design/ADR_002_black_box_api_scope.md) | [core.py](../src/p3_core/mock_api/core.py)、[reviewed_protocol.py](../src/p3_core/http/reviewed_protocol.py) | [test_three_defects_both_strategies](../tests/test_remaining.py)、[test_entire_declared_matrix_and_single_defect_isolation](../tests/test_mock_api.py) | [F](#evidence-f)、[S](#evidence-s) | F2：711550a + 审核补丁（代码字节对应 7178dbb）；NOT_FULLY_BOUND（36 次） | F2 ZIP，未入 Git 的日志；9754048 归档基线；04214d3 路径提交 | 旧角色夹具子例及声明矩阵隔离 | 已实现／自动验证／提交（离线） | 待负责人／适用时 P1 | PENDING_TEACHER_CONFIRMATION | V2 当前两套样例未替代该角色子例 | P3 负责人（夹具与契约） |
| P3-REQ-007 | Controller 独立于 Planner 和 LLM 作授权决定；执行器只经强制入口派发。 | MUST | GWT-A01、GWT-A02 | [ADR-001](../design/ADR_001_controller_split.md) | [controller.py](../src/p3_core/controller.py)、[reviewed_runtime.py](../src/p3_core/http/reviewed_runtime.py) | [test_controller_denies_unapproved_candidate](../tests/test_c3d_host.py)、[test_bad_selector_fails_closed](../tests/test_remaining.py) | [F](#evidence-f)、[A](#evidence-a)、[B](#evidence-b)、[D](#evidence-d) | F2：711550a + 审核补丁（代码字节对应 7178dbb）；67242ba 原样执行；67242ba + 当次工作区差异与文件哈希；5a6e81a + 当时状态；评价执行 | F2 ZIP，未入 Git 的日志；5c16b2b（证据目录路径提交）；5c16b2b（证据目录路径提交）；8019021（评价输出移交） | 未批准提案拒绝，无对应模拟派发 | 已实现／自动验证／提交（离线） | 待负责人／适用时 P1 | PENDING_TEACHER_CONFIRMATION | 无进程隔离或 OS 未派发证明 | P3 负责人（Controller） |
| P3-REQ-008 | 严格验证意图类型、字段、端点、方法、身份及参数组合；非法意图拒绝并记原因。 | MUST | GWT-N03 | [ADR-002](../design/ADR_002_black_box_api_scope.md) | [contract.py](../src/p3_core/http/contract.py)、[adapter.py](../src/p3_core/mock_api/adapter.py)、[reviewed_protocol.py](../src/p3_core/http/reviewed_protocol.py) | [test_adapter_rejects_header_and_target_mutations](../tests/test_remaining.py)、[test_parameter_domain_enforced](../tests/test_reviewed_protocol.py) | [F](#evidence-f)、[A](#evidence-a)、[B](#evidence-b) | F2：711550a + 审核补丁（代码字节对应 7178dbb）；67242ba 原样执行；67242ba + 当次工作区差异与文件哈希 | F2 ZIP，未入 Git 的日志；5c16b2b（证据目录路径提交）；5c16b2b（证据目录路径提交） | 本地不合法组合拒绝及 R01 拒绝链 | 已实现／自动验证／提交（离线） | 待负责人／适用时 P1 | PENDING_TEACHER_CONFIRMATION | 未测试真实目标输入路径 | P3 负责人（Controller 与契约） |
| P3-REQ-009 | 不可信响应不能修改授权／预算；授权运行中只能撤销，扩权必须重新批准并启动新运行。 | MUST | GWT-A01 | [ADR-001](../design/ADR_001_controller_split.md) | [machine.py](../src/p3_core/http/machine.py)、[reviewed_snapshot.py](../src/p3_core/http/reviewed_snapshot.py) | [test_late_response_during_read_cannot_upgrade](../tests/test_http_core.py)、[test_object_setattr_cannot_change_authorisation_fields](../tests/test_reviewed_snapshot.py) | [F](#evidence-f) | F2：711550a + 审核补丁（代码字节对应 7178dbb） | F2 ZIP，未入 Git 的日志 | 迟到响应与只读快照不扩大权限 | 已实现／自动验证／提交（离线） | 待负责人／适用时 P1 | PENDING_TEACHER_CONFIRMATION | 测试边界在应用层；真实材料外部真实性未核验 | P3 负责人（授权与执行协调） |
| P3-REQ-010 | 实施第 4 节的计数、逻辑时间、并发及无新增证据停止规则；不得通过拒绝、重试或时钟跳变逃避限制。数字预算试跑后遵循教师冻结。 | MUST | GWT-N04、GWT-N05、GWT-A01 | [ADR-004](../design/ADR_004_http_dispatch_and_cancellation.md) | [machine.py](../src/p3_core/http/machine.py)、[reviewed_runtime.py](../src/p3_core/http/reviewed_runtime.py)、[reviewed_evidence.py](../src/p3_core/http/reviewed_evidence.py) | [test_denials_consume_budget_and_eighth_ninth_boundary](../tests/test_http_core.py)、[test_budget_smaller_than_candidates](../tests/test_reviewed_evidence.py)、[test_budget_larger_than_candidates](../tests/test_reviewed_evidence.py) | [F](#evidence-f)、[Q](#evidence-q) | F2：711550a + 审核补丁（代码字节对应 7178dbb）；711550a 对应 3B-2A 交付；见范围评审及已存验收摘录 | F2 ZIP，未入 Git 的日志；711550a（设计/说明归档；本地原始日志未入 Git） | 累计预算、候选与预算分离、范围事件交叉核对 | 已实现／自动验证／提交（离线） | 待负责人／适用时 P1 | PENDING_TEACHER_CONFIRMATION | 8／90／1 为试跑；不证明真实时延或班级冻结 | P3 负责人（预算与运行） |
| P3-REQ-011 | 支持撤权停止，新派发前核验撤权；记录在途取消及未完成范围。 | MUST | GWT-A03 | [ADR-004](../design/ADR_004_http_dispatch_and_cancellation.md) | [machine.py](../src/p3_core/http/machine.py)、[reviewed_runtime.py](../src/p3_core/http/reviewed_runtime.py) | [test_partial_send_then_revocation_retains_one_model_send](../tests/test_remaining.py)、[test_revoke_between_accept_and_consume_aborts_ticket](../tests/test_reviewed_runtime.py) | [F](#evidence-f)、[C](#evidence-c) | F2：711550a + 审核补丁（代码字节对应 7178dbb）；3199b3f 起始基线 + 当次工作区增量 | F2 ZIP，未入 Git 的日志；8019021（日志移交） | 内存分段派发、撤权、中止与旧监督记录 | 已实现／自动验证／提交（离线） | 待负责人／适用时 P1 | PENDING_TEACHER_CONFIRMATION | 真实在途与 OS 撤权时延未测 | P3 负责人（撤权与运行） |
| P3-REQ-012 | 在授权不明、连接故障、超时、运行异常或审计写入失败时安全停止，不自动扩权或盲目重试。 | MUST | GWT-N01、GWT-N05、GWT-N06 | [ADR-004](../design/ADR_004_http_dispatch_and_cancellation.md) | [audit.py](../src/p3_core/http/audit.py)、[reviewed_runtime.py](../src/p3_core/http/reviewed_runtime.py) | [test_faults_do_not_confirm_leaks](../tests/test_remaining.py)、[test_audit_failure_blocks_new_fixture_work](../tests/test_reviewed_runtime.py)、[test_scope_event_failure_stops_before_dispatch](../tests/test_reviewed_runtime.py) | [F](#evidence-f)、[C](#evidence-c) | F2：711550a + 审核补丁（代码字节对应 7178dbb）；3199b3f 起始基线 + 当次工作区增量 | F2 ZIP，未入 Git 的日志；8019021（日志移交） | 合成故障、证据失败时停止且不确认违规 | 已实现／自动验证／提交（离线） | 待负责人／适用时 P1 | PENDING_TEACHER_CONFIRMATION | 真实连接异常与关闭尚未验收 | P3 负责人（运行与审计） |
| P3-REQ-013 | 通过 Executor 获取实际本地请求响应证据，不以模拟成功消息替代已执行事实。 | MUST | GWT-P01、GWT-N06 | [ADR-004](../design/ADR_004_http_dispatch_and_cancellation.md) | [live.py](../src/p3_core/http/live.py) | [test_transport_methods_with_fake_socket_only](../tests/test_remaining.py) | [F](#evidence-f)、[H](#evidence-h) | F2：711550a + 审核补丁（代码字节对应 7178dbb）；真实执行无 | F2 ZIP，未入 Git 的日志；不适用；现有 JSON 为待授权状态清单 | 仅静态/替身检查，实际请求响应证据未执行 | PARTIAL：组件已提交；替身已自动验证 | 待负责人／适用时 P1 | PENDING_TEACHER_CONFIRMATION | 正式真实场景仍 PENDING_AUTHORIZATION；H4 课程处置待 A-05 | P3 负责人（受控执行与授权） |
| P3-REQ-014 | 分开记录授权、执行和测试结论，按第 5 节判定，证据不足不得通过。 | MUST | GWT-P01、GWT-P02、GWT-N02、GWT-N07 | [ADR-003](../design/ADR_003_local_execution_and_evidence.md) | [protocol.py](../src/p3_core/http/protocol.py)、[reviewed_evidence.py](../src/p3_core/http/reviewed_evidence.py)、[reviewed_metrics.py](../src/p3_core/http/reviewed_metrics.py) | [test_deny_candidate_requires_control_for_pass](../tests/test_reviewed_protocol.py)、[test_f2_direct_projection_requires_protocol_types](../tests/test_reviewed_metrics.py) | [F](#evidence-f)、[A](#evidence-a)、[B](#evidence-b) | F2：711550a + 审核补丁（代码字节对应 7178dbb）；67242ba 原样执行；67242ba + 当次工作区差异与文件哈希 | F2 ZIP，未入 Git 的日志；5c16b2b（证据目录路径提交）；5c16b2b（证据目录路径提交） | R01 的三状态分离；V2 空值、类型与结论门槛 | 已实现／自动验证／提交（离线） | 待负责人／适用时 P1 | PENDING_TEACHER_CONFIRMATION | 对模拟结论的核验不等同真实 API 判定 | P3 负责人（评价与证据） |
| P3-REQ-015 | 关联记录允许、拒绝、错误、撤权、预算与停止事件，使用唯一运行／检查／动作标识，禁止同秒覆盖。 | MUST | GWT-P03、GWT-N03、GWT-A03 | [ADR-003](../design/ADR_003_local_execution_and_evidence.md) | [evidence.py](../src/p3_core/evidence.py)、[audit.py](../src/p3_core/http/audit.py)、[reviewed_evidence.py](../src/p3_core/http/reviewed_evidence.py) | [test_unique_ids_and_no_overwrite](../tests/test_http_core.py)、[test_report_tamper_rejected](../tests/test_remaining.py)、[test_result_counts_block_must_match_replay](../tests/test_reviewed_evidence.py) | [F](#evidence-f)、[A](#evidence-a)、[B](#evidence-b)、[Q](#evidence-q) | F2：711550a + 审核补丁（代码字节对应 7178dbb）；67242ba 原样执行；67242ba + 当次工作区差异与文件哈希；711550a 对应 3B-2A 交付；见范围评审及已存验收摘录 | F2 ZIP，未入 Git 的日志；5c16b2b（证据目录路径提交）；5c16b2b（证据目录路径提交）；711550a（设计/说明归档；本地原始日志未入 Git） | ID 关联、原始 R01 的完整性差异、V2 计数重放 | 已实现／自动验证／提交（离线） | 待负责人／适用时 P1 | PENDING_TEACHER_CONFIRMATION | 首次 R01 的完整性失败仍有效；摘要不认证来源 | P3 负责人（证据与审计） |
| P3-REQ-016 | 凭据仅用引用，证据脱敏且标记缺失／截断；真实与模拟数据及成本不得混淆。 | MUST | GWT-P03、GWT-N07 | [ADR-003](../design/ADR_003_local_execution_and_evidence.md) | [protocol.py](../src/p3_core/http/protocol.py)、[reviewed_protocol.py](../src/p3_core/http/reviewed_protocol.py)、[reviewed_evidence.py](../src/p3_core/http/reviewed_evidence.py) | [test_artifacts_never_contain_credentials_parameters_or_exception_body](../tests/test_http_core.py)、[test_projection_keeps_only_evidence_fields](../tests/test_reviewed_protocol.py) | [F](#evidence-f)、[B](#evidence-b) | F2：711550a + 审核补丁（代码字节对应 7178dbb）；67242ba + 当次工作区差异与文件哈希 | F2 ZIP，未入 Git 的日志；5c16b2b（证据目录路径提交） | 本地合成字段投影与扫描，模拟计数单列 | 已实现／自动验证／提交（离线） | 待负责人／适用时 P1 | PENDING_TEACHER_CONFIRMATION | 不主张真实流量测量或通用脱敏 | P3 负责人（证据与隐私） |
| P3-REQ-017 | 报告仅对已检查范围给出有限结论，列出未决和未覆盖范围，不能声称整个系统安全。 | MUST | GWT-N04、GWT-N07、GWT-A03 | [ADR-003](../design/ADR_003_local_execution_and_evidence.md) | [offline_summary.py](../src/p3_core/offline_summary.py)、[reviewed_metrics.py](../src/p3_core/http/reviewed_metrics.py) | [test_faults_do_not_confirm_leaks](../tests/test_remaining.py)、[test_unlinked_assertion_is_not_counted](../tests/test_reviewed_metrics.py) | [F](#evidence-f)、[B](#evidence-b)、[Q](#evidence-q) | F2：711550a + 审核补丁（代码字节对应 7178dbb）；67242ba + 当次工作区差异与文件哈希；711550a 对应 3B-2A 交付；见范围评审及已存验收摘录 | F2 ZIP，未入 Git 的日志；5c16b2b（证据目录路径提交）；711550a（设计/说明归档；本地原始日志未入 Git） | 输出未覆盖/未决；关联不足不给有效指标 | 已实现／自动验证／提交（离线） | 待负责人／适用时 P1 | PENDING_TEACHER_CONFIRMATION | 无法由有限证据推断整个系统安全 | P3 负责人（报告与评价） |
| P3-REQ-018 | 模拟环境具有可重置身份／角色／对象夹具，支持正确拒绝与已知权限缺陷的可重复验收。 | MUST | GWT-P02、GWT-N02、GWT-P04 | [ADR-002](../design/ADR_002_black_box_api_scope.md) | [core.py](../src/p3_core/mock_api/core.py)、[catalog_fixture.py](../src/p3_core/http/catalog_fixture.py) | [test_entire_declared_matrix_and_single_defect_isolation](../tests/test_mock_api.py)、[test_two_scenarios_are_independent](../tests/test_catalog_fixture.py) | [F](#evidence-f)、[S](#evidence-s) | F2：711550a + 审核补丁（代码字节对应 7178dbb）；NOT_FULLY_BOUND（36 次） | F2 ZIP，未入 Git 的日志；9754048 归档基线；04214d3 路径提交 | 旧三类可重置夹具与 documents/directories 内存样例 | 已实现／自动验证／提交（离线） | 待负责人／适用时 P1 | PENDING_TEACHER_CONFIRMATION | V2 两个样例并不替代旧策略实验或完整真实验收 | P3 负责人（夹具与复现） |
| P3-REQ-019 | 用配置和命令行入口完成运行与报告读取，不要求图形界面；说明输入错误及停止原因。 | SHOULD | GWT-P04、GWT-N01 | [ADR-003](../design/ADR_003_local_execution_and_evidence.md) | [delivery.py](../src/p3_core/delivery.py)、[evaluator.py](../src/p3_core/evaluator.py) | [test_cli_validate_does_not_grant_permission](../tests/test_remaining.py)、[test_cli_and_read_only](../tests/test_offline_summary.py#L72) | [F](#evidence-f)、[E](#evidence-e) | F2：711550a + 审核补丁（代码字节对应 7178dbb）；5a6e81a + 当时状态；评价执行 | F2 ZIP，未入 Git 的日志；8019021（评价输出移交） | validate 对测试配置返回 0 且仍为 PENDING_AUTHORIZATION；推荐 CLI 对既有运行执行 offline --run、在合成场景执行 offline --output，两分支均返回 0，且既有证据目录中文件字节不变。E 仅记录历史评价器只读调用 | 已实现／自动验证／提交（离线） | 待负责人／适用时 P1 | PENDING_TEACHER_CONFIRMATION | --output 用例检查生成分支成功，未逐字段核对新报告；--run 用例不证明跨环境可移植性，伙伴环境待核验。V2 指标为 Python 接口 | P3 负责人（交付与文档） |
| P3-REQ-020 | 为后续策略对比记录策略版本、候选集合、夹具版本、相同预算、实际请求数、覆盖和有据结果；不伪造比较结果。 | MUST | GWT-P04 | [ADR-005](../design/ADR_005_deterministic_strategy_comparison.md) | [experiments.py](../src/p3_core/experiments.py)、[reviewed_evidence.py](../src/p3_core/http/reviewed_evidence.py) | [test_comparison_records_actual_observations](../tests/test_remaining.py)、[test_s1_scope_binding_is_consistent](../tests/test_reviewed_evidence.py) | [F](#evidence-f)、[S](#evidence-s)、[Q](#evidence-q) | F2：711550a + 审核补丁（代码字节对应 7178dbb）；NOT_FULLY_BOUND（36 次）；711550a 对应 3B-2A 交付；见范围评审及已存验收摘录 | F2 ZIP，未入 Git 的日志；9754048 归档基线；04214d3 路径提交；711550a（设计/说明归档；本地原始日志未入 Git） | 历史策略元数据；V2 内部范围绑定可补追溯 | PARTIAL：离线元数据已提交并验证 | 待负责人／适用时 P1 | PENDING_TEACHER_CONFIRMATION | 历史逐次版本/环境未完全绑定；实际网络请求未实测 | P3 负责人（策略与证据） |
| P3-REQ-021 | 基础闭环后比较固定顺序与基于既有结果的确定性动态选择策略，采用相同输入、声明目标、授权、重置夹具及预算；报告覆盖、检出、误确认、未确定、工具故障、越界动作、成本和规划开销，并以 ADR 记录采用／限制采用／保留固定／需要更多证据。依据 S3 37、42、46、73、99 的课程任务映射，不预设动态更优。 | MUST | GWT-P05 | [ADR-005](../design/ADR_005_deterministic_strategy_comparison.md) | [strategies.py](../src/p3_core/http/strategies.py)、[experiments.py](../src/p3_core/experiments.py) | [test_comparison_records_actual_observations](../tests/test_remaining.py)、[test_strategy_repeatable](../tests/test_remaining.py) | [F](#evidence-f)、[S](#evidence-s) | F2：711550a + 审核补丁（代码字节对应 7178dbb）；NOT_FULLY_BOUND（36 次） | F2 ZIP，未入 Git 的日志；9754048 归档基线；04214d3 路径提交 | 36 次历史策略记录，ADR-005 有限工程接受 | PARTIAL：离线对照已提交，正式验收未完成 | 待负责人／适用时 P1 | PENDING_TEACHER_CONFIRMATION | 事前卡未形成；准备/复核成本未测；每格 3 次；P1 未复现 | P3 负责人（策略实验） |
| P3-REQ-022 | 基础验收后经负责人另行决策、满足数据与成本授权后可接入真实 LLM；不得改变 Controller 权限边界，真实成本单独计量。 | MAY | GWT-A04（后续） | [ADR-001](../design/ADR_001_controller_split.md) | 未接入 | 未接入；[RC2 可选范围](../brief/P3_specification_v1.0-rc2.md) | [GWT-A04（后续）](P3_GWT_scenarios.md)；无实际 LLM 运行原件 | 无实际 LLM 执行 | 不适用，无 LLM 运行原件 | 真实 LLM 可选后续，本次无执行 | NOT_STARTED（MAY；当前范围外） | 待范围确认 | 可选；未申报正式验收 | 未接入、没有执行证据，无数据/成本授权 | P3 负责人（项目范围与授权） |

## 6B-5B-2 P1 Finding 追踪附录

此附录为非规范性导航，原 22 项需求矩阵、16 个字段及正式场景定义继续适用。下列关联仅用于查找局部证据，完整 HTTP 场景仍为 PENDING_AUTHORIZATION。本轮产品测试、模拟及实验为 NOT_REEXECUTED。[P1 原登记](../review/P3_6b5a_peer_finding_register.md) · [回传验收与冻结版本](../review/P3_6b5a_peer_return_acceptance.md)

### C-05 场景导航

RC2 §8 的 19 行为 16 个主场景与 A01-a／b／c。GWT §2／§3 共 32 行，其余 13 行为既有细化。父子关系沿用原编号。关联 REQ 取自主场景追踪或子行自带标注。A01-a～c 通过父场景关联 REQ-010，原条款仍以 RC2 §4 项9 为准。适用版本列说明证据切片，整张表的规范基线都是 RC2。V1 合成指旧 HTTP 模型切片，历史离线指旧核心无 HTTP 验证，V2 子集指独立列出的范围或审查记录。

证据入口 [L 离线核心验证](P3_offline_core_validation.md)、[F 既有回归](#evidence-f)、[B R01 整改后](#evidence-b)、[S 历史策略对照](#evidence-s)、[P P1 冻结版记录](../review/P3_6b5a_peer_return_acceptance.md)、[H 真实执行缺口](#evidence-h)。REQ 编号可在主矩阵定位原证据。下表的限制列适用于各行，任何已有离线证据均不提升完整场景验收状态。

| 场景 ID | 父场景 | RC2 位置 | GWT 位置 | 关联 REQ | 适用版本 | 已有证据入口 | 验收状态及限制 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GWT-P01 | — | [§8 L145](../brief/P3_specification_v1.0-rc2.md) | [L22](P3_GWT_scenarios.md) | 002 / 013 / 014 | V1 合成 | [F](#evidence-f)、正向说明 | 许可与合成响应断言；无实际请求响应验收 |
| GWT-P02 | — | [§8 L146](../brief/P3_specification_v1.0-rc2.md) | [L23](P3_GWT_scenarios.md) | 004 / 005 / 006 / 014 / 018 | V1 合成 | [F](#evidence-f)、正向说明 | 三类预期拒绝与对照条件的合成判定；真实配对待授权 |
| GWT-P03 | — | [§8 L147](../brief/P3_specification_v1.0-rc2.md) | [L24](P3_GWT_scenarios.md) | 015 / 016 | 历史离线／V1 合成 | [L](P3_offline_core_validation.md)、[F](#evidence-f)（REQ-015／016） | 唯一 ID、防覆盖及脱敏的应用层断言；无完整实跑 |
| GWT-P04 | — | [§8 L148](../brief/P3_specification_v1.0-rc2.md) | [L25](P3_GWT_scenarios.md) | 003 / 018 / 019 / 020 | 历史离线／V1 合成 | [L](P3_offline_core_validation.md)、[F](#evidence-f)（REQ-003／019／020） | 确定性规划、离线入口与元数据有局部证据；正式比较另列 |
| GWT-P05 | — | [§8 L149](../brief/P3_specification_v1.0-rc2.md) | [L26](P3_GWT_scenarios.md) | 003 / 020 / 021（003 取自 RC2 需求表，020／021 见 GWT L26） | V1 历史合成 | [S](#evidence-s)、[P](../review/P3_6b5a_peer_return_acceptance.md) | 36 次历史离线对照为 NOT_FULLY_BOUND。P1 冻结版 103a9ed 的 Good 配对为独立记录。当前工程版 7178dbb 单列，两批记录均无完整成本比较或策略优势证明。REQ-021 正式验收待办 |
| GWT-N01 | — | [§8 L150](../brief/P3_specification_v1.0-rc2.md) | [L27](P3_GWT_scenarios.md) | 001 / 012 / 019 | 历史离线／V1、V2 子集 | [L](P3_offline_core_validation.md)、[F](#evidence-f)（REQ-001） | 预检无规划／无派发及 V2 矩阵冲突；离线局部支持 |
| GWT-N02 | — | [§8 L151](../brief/P3_specification_v1.0-rc2.md) | [L28](P3_GWT_scenarios.md) | 004 / 005 / 006 / 014 / 018 | V1 合成 | [F](#evidence-f)（REQ-004～006） | 三类合成缺陷样例；实际响应与全部变体未验收 |
| GWT-N03 | — | [§8 L152](../brief/P3_specification_v1.0-rc2.md) | [L29](P3_GWT_scenarios.md) | 008 / 015 | 历史离线／V1 合成 | [L](P3_offline_core_validation.md)、[B](#evidence-b)、[F](#evidence-f)（REQ-008） | 输入校验和未批准提案拒绝为局部材料，各参数分支需分别举证 |
| GWT-N04 | — | [§8 L153](../brief/P3_specification_v1.0-rc2.md) | [L30](P3_GWT_scenarios.md) | 010 / 017 | 历史离线／V1 合成 | [L](P3_offline_core_validation.md)、[F](#evidence-f)（REQ-010） | 累计预算、拒绝、终态为局部证据；V2 槽位语义不套用 |
| GWT-N05 | — | [§8 L154](../brief/P3_specification_v1.0-rc2.md) | [L31](P3_GWT_scenarios.md) | 010 / 012 | 历史离线 | [L](P3_offline_core_validation.md) | 可控时钟、预算、回拨为局部证据；真实等待或并发未验收 |
| GWT-N06 | — | [§8 L155](../brief/P3_specification_v1.0-rc2.md) | [L32](P3_GWT_scenarios.md) | 012 / 013 | V1 合成 | [F](#evidence-f)（REQ-012）、来源说明 | 合成故障安全停止有证据；正式停止规则语义待确认 |
| GWT-N07 | — | [§8 L156](../brief/P3_specification_v1.0-rc2.md) | [L33](P3_GWT_scenarios.md) | 014 / 016 / 017 | 历史离线／V1、V2 子集 | [B](#evidence-b)、[F](#evidence-f)（REQ-014／017） | R01 拒绝及 V2 缺对照／缺关联的保守结论；无完整实跑 |
| GWT-A01 | — | [§8 L157](../brief/P3_specification_v1.0-rc2.md) | [L34](P3_GWT_scenarios.md) | 007 / 009 / 010 | 历史离线／V1、V2 子集 | [L](P3_offline_core_validation.md)、[F](#evidence-f)（REQ-007／009） | 不扩权与防提前停止仅覆盖所列控制分支 |
| GWT-A02 | — | [§8 L158](../brief/P3_specification_v1.0-rc2.md) | [L35](P3_GWT_scenarios.md) | 002 / 007 | 历史离线／V1 合成 | [L](P3_offline_core_validation.md)、[F](#evidence-f)（REQ-002／008） | 本地范围、输入及替换拒绝的局部证据；无真实转发验收 |
| GWT-A03 | — | [§8 L159](../brief/P3_specification_v1.0-rc2.md) | [L36](P3_GWT_scenarios.md) | 011 / 015 / 017 | 历史离线／V1、V2 子集 | [L](P3_offline_core_validation.md)、[F](#evidence-f)（REQ-011）、授权说明 | 撤权、模型发送与接受后消费前中止分列；授权到期另见说明 |
| GWT-A04 | — | [§8 L160](../brief/P3_specification_v1.0-rc2.md) | [L37](P3_GWT_scenarios.md) | 022 | 可选真实 LLM | [H](#evidence-h)（仅状态） | 未接入；无执行原件 |
| GWT-N04-a | GWT-N04 | [§8 GWT-N04 L153](../brief/P3_specification_v1.0-rc2.md)（子行仅在 GWT） | [L43](P3_GWT_scenarios.md) | 010 / 015 / 017 | 历史离线 | [L](P3_offline_core_validation.md) | 8 尝试、7 假派发、实际 HTTP 0；原场景 request_count=7 未验证 |
| GWT-N04-b | GWT-N04 | [§8 GWT-N04 L153](../brief/P3_specification_v1.0-rc2.md)（子行仅在 GWT） | [L44](P3_GWT_scenarios.md) | 010 / 017 | 历史离线／V1 合成 | [L](P3_offline_core_validation.md)、[F](#evidence-f)（REQ-010） | 达到 8 后超限停止有局部证据；不把其他运行的计数当该变体 |
| GWT-N04-c | GWT-N04 | [§8 GWT-N04 L153](../brief/P3_specification_v1.0-rc2.md)（子行仅在 GWT） | [L45](P3_GWT_scenarios.md) | 010 / 014 / 017 | 历史离线 | [L](P3_offline_core_validation.md) | 终态不重开及 8／9 边界有局部证据；待决追加和结束时点应区分 |
| GWT-N04-d | GWT-N04 | [§8 GWT-N04 L153](../brief/P3_specification_v1.0-rc2.md)（子行仅在 GWT） | [L46](P3_GWT_scenarios.md) | 008 / 010 / 015 | 历史离线／V1 合成 | [L](P3_offline_core_validation.md)、[F](#evidence-f)（REQ-010） | 旧入口失败提案的累计名额有局部证据；V2 计数口径待负责人 |
| GWT-N04-e | GWT-N04 | [§8 GWT-N04 L153](../brief/P3_specification_v1.0-rc2.md)（子行仅在 GWT） | [L47](P3_GWT_scenarios.md) | 008 / 010 / 015 | 历史离线／V1 合成 | [L](P3_offline_core_validation.md) | 历史重复／替换拒绝留存，原项不应重复计数；V2 另列 |
| GWT-N04-f | GWT-N04 | [§8 GWT-N04 L153](../brief/P3_specification_v1.0-rc2.md)（子行仅在 GWT） | [L48](P3_GWT_scenarios.md) | 010 / 014 | 历史离线／V1 合成 | [L](P3_offline_core_validation.md)、[F](#evidence-f)（REQ-014） | 拒绝时的保守结论和正常完成条件分别有材料；未据此确认完整时序变体 |
| GWT-N05-a | GWT-N05 | [§8 GWT-N05 L154](../brief/P3_specification_v1.0-rc2.md)（子行仅在 GWT） | [L49](P3_GWT_scenarios.md) | 010 / 012 | 历史离线 | [L](P3_offline_core_validation.md) | 含首次规划耗尽的可控时钟结果；无真实计时证明 |
| GWT-N05-b | GWT-N05 | [§8 GWT-N05 L154](../brief/P3_specification_v1.0-rc2.md)（子行仅在 GWT） | [L50](P3_GWT_scenarios.md) | 010 / 012 | 历史离线 | [L](P3_offline_core_validation.md) | 仅注入回调耗时；真实剩余超时及取消未验证 |
| GWT-N05-c | GWT-N05 | [§8 GWT-N05 L154](../brief/P3_specification_v1.0-rc2.md)（子行仅在 GWT） | [L51](P3_GWT_scenarios.md) | 010 / 014 | 历史离线 | [L](P3_offline_core_validation.md) | 89／90 秒及证据耗时的验证记录；不外推真实执行 |
| GWT-N05-d | GWT-N05 | [§8 GWT-N05 L154](../brief/P3_specification_v1.0-rc2.md)（子行仅在 GWT） | [L52](P3_GWT_scenarios.md) | 010 | 历史离线 | [L](P3_offline_core_validation.md) | 墙钟回拨不延长单调时钟预算；无真实网络测量 |
| GWT-A03-a | GWT-A03 | [§8 GWT-A03 L159](../brief/P3_specification_v1.0-rc2.md)（子行仅在 GWT） | [L53](P3_GWT_scenarios.md) | 010 / 011 / 015 | 历史离线 | [L](P3_offline_core_validation.md) | 多原因优先有离线材料；未作真实在途或 OS 层验证 |
| GWT-P05-a | GWT-P05 | [§8 GWT-P05 L149](../brief/P3_specification_v1.0-rc2.md)（子行仅在 GWT） | [L54](P3_GWT_scenarios.md) | 020 / 021 | V1 历史合成／文档核查 | [S](#evidence-s)、[P](../review/P3_6b5a_peer_return_acceptance.md) | 历史内部取舍存在，C-02 未全部完成，正式比较验收待办 |
| GWT-P05-b | GWT-P05 | [§8 GWT-P05 L149](../brief/P3_specification_v1.0-rc2.md)（子行仅在 GWT） | [L55](P3_GWT_scenarios.md) | 020 / 021 | V1 历史合成 | [S](#evidence-s)、[P](../review/P3_6b5a_peer_return_acceptance.md) | 已有历史对照和冻结版 Good 配对；正式可比条件与完整成本证据待验收 |
| GWT-A01-a | GWT-A01 | [§8 L168](../brief/P3_specification_v1.0-rc2.md) | [L65](P3_GWT_scenarios.md) | 010 / 014 / 017（[GWT L61 共同映射](P3_GWT_scenarios.md)） | 历史离线 | [L](P3_offline_core_validation.md) | 无价值重复控制分支有历史证据；完整 HTTP 未执行 |
| GWT-A01-b | GWT-A01 | [§8 L169](../brief/P3_specification_v1.0-rc2.md) | [L66](P3_GWT_scenarios.md) | 010 / 014 / 017（[GWT L61 共同映射](P3_GWT_scenarios.md)） | 历史离线 | [L](P3_offline_core_validation.md) | 仍有候选时不提前停止；测试为无响应假派发 |
| GWT-A01-c | GWT-A01 | [§8 L170](../brief/P3_specification_v1.0-rc2.md) | [L67](P3_GWT_scenarios.md) | 010 / 014 / 017（[GWT L61 共同映射](P3_GWT_scenarios.md)） | 历史离线 | [L](P3_offline_core_validation.md) | 必要对照不被跳过；未验证真实 403／404 及其判定 |

### C-06 不变量追踪

定义来自 [Problem Frame §4](../brief/P3_problem_frame.md)。关联依据为 [RC2 §6 的分组](../brief/P3_specification_v1.0-rc2.md) 及各行列明的 GWT 条件。以下为 P3 的局部证据索引，保留原定义及原判定范围。

| INV | 原始定义 | 关联 REQ | 关联 GWT | 已有验证证据 | 验证范围 | 剩余限制 |
| --- | --- | --- | --- | --- | --- | --- |
| INV-01 | Controller 否决优先：未经完整授权核验的请求不得发送。 | 007／008／011／012 | N01、N03、A02、A03 | [R01](#evidence-b)、[F](#evidence-f) REQ-007／011、下方授权说明 | 记录中未批准候选 DENY、无对应 action，以及 V2 到期后未消费 | 应用层和内存证据，缺独立 OS 未发送及真实授权证明 |
| INV-02 | 授权不可由不可信数据扩大：目标响应、意图和错误反馈均不能修改政策或预算。 | 007～010 | A01、A02、N03 | [F](#evidence-f) REQ-009／010、[范围绑定](#evidence-q) | 只读快照的授权字段不可变，预算约束与审核候选范围绑定有独立离线证据。迟到响应测试仅补充撤权停止与结论边界（REVOKED，模拟结论仍为 INCONCLUSIVE），未直接比对响应前后的授权字段或预算 | 缺同进程任意代码隔离及真实权限验收 |
| INV-03 | 结论诚实：EXECUTED 不等于 PASS；证据不足、被阻断或未执行的用例为 INCONCLUSIVE。 | 014～017 | N02、N07、P03 | [R01 首次](#evidence-a)、[R01 整改后](#evidence-b)、[F](#evidence-f) REQ-014／017 | 保留证据不足和拒绝的结论，未关联断言不作有效指标 | 保留真实执行和模拟结论的区分，摘要不认证来源 |
| INV-04 | 撤权或预算到达停止条件后不得派发新请求；已发送请求不能被追溯撤销。 | 010～012 | N04、N05、A03、A03-a | [离线核心](P3_offline_core_validation.md)、[F](#evidence-f) REQ-010／011 | 预算边界、模型分段发送和消费前中止为局部证据 | 缺真实在途取消、时延与 OS 层验证 |
| INV-05 | 检查仅使用已批准的本地模拟目标、模拟身份和只读资源；证据不得泄露原始凭据。 | 002／016，补充 008 输入边界 | P01、A02、P03 | [F](#evidence-f) REQ-002／008／016 | 合成许可不能进入真实模式，所测字段投影与凭据扫描受限 | 缺真实目标验收及通用脱敏证明 |

### C-09 REQ-001 正向关联说明

- **N01 原正式关联保持。** REQ-001 主行证据支持缺契约或矩阵冲突时的预检拒绝，所列预检用例断言无计划，V2 用例断言拒绝冲突矩阵。完整 N01 场景仍沿用原定义。
- **P01 部分正向关联。** 批准的只读输入、矩阵预期 ALLOW 与契约响应对应 REQ-001 的有效输入和基于契约检查。下方历史合成测试对预期允许内容给出模拟 PASS；原 P01 的实际响应、EXECUTED 和单次真实派发没有验收证据。
- **P02 部分正向关联。** 已批准的检查、预期拒绝矩阵和合法对照共同体现基于契约验证预期权限。下方单元测试以已满足对照条件求值，另外可参阅主矩阵 REQ-005 对照不足时的断言。实际拒绝响应、独立成功对照与请求计数仍待正式验收。两场景实际 HTTP 均维持 PENDING_AUTHORIZATION。

### C-01 已有授权证据导航

RC2 §4 项7及 §7 已区分授权失效与可信撤权，同一检查点的撤权优先于授权失效。N01 处理缺失授权等静态输入问题，A03／A03-a 处理可信撤权与仲裁。GWT 目前没有独立 AUTHORIZATION_INVALID 到期场景。REQ-011／012 可由此定位现有启动到期和运行中到期证据。完整正式到期场景、适用协议、原因码验收与真实在途处理仍待批准。V2 已接受的 Ticket 在消费前过期的证据支持未消费、已中止、夹具未启动，接受记录仍保留。

| 附录测试引用 | 代码及断言范围 | 既有日志 |
| --- | --- | --- |
| [test_expiration_during_run](../tests/test_core.py#L311) | 旧核心在运行中到期，AUTHORIZATION_INVALID，8 个计划、0 尝试、0 假派发 | F2 实施与第三轮独立技术审核 full.log 各第 155 行 |
| [test_expired_licence_blocks_start](../tests/test_reviewed_runtime.py#L263) | V2 已绑定许可过期时 STOPPED、AUTHORIZATION_INVALID、无夹具启动 | 两份 full.log 各第 573 行 |
| [test_licence_expiry_between_accept_and_consume_aborts_ticket](../tests/test_reviewed_runtime.py#L436) | V2 接受计数 1，过期后无消费、中止 1、无夹具启动且原因为 AUTHORIZATION_INVALID | 两份 full.log 各第 578 行 |
| [test_good_three_denials_and_controls](../tests/test_http_core.py#L200) | C-09 的 V1 正向／预期拒绝合成断言。对照布尔值传入为真，断言模拟 PASS 而实际执行状态保持 NOT_EXECUTED、结论 INCONCLUSIVE | 两份 full.log 各第 307 行 |

四个方法按模块、类、方法核对源码与历史日志，执行身份仍为 711550a 加 F2 工作区补丁，源码与 7178dbb 对应。主矩阵的 36 个方法保持原样，附录另增 4 个不同方法，全文去重为 40。没有新增自动化用例或运行。

### C-02 RC1 来源说明

原 P1 Finding 与原分级保留。原冻结分发 ZIP 的 SHA-256 为 `ffa669b4654232b025dfb3018e088241c0b787a7932024a579ac7899a6022f72`。其中 `P1_P3_Complete_Review/Frozen_Snapshot/brief/P3_specification_v1.0-rc1.md` 实测 27,610 字节，SHA-256 为 `e3cec25af32ee5f8efc53d13833a354792137527e012511d3a4a572d1083e418`，与 P1 冻结提交 103a9ed 的 Git 对象和当前 RC1 文件逐字节一致。「冻结包没有 RC1」这一原观察由原件校核更正，原 P1 回传文档及 Finding 未改。

规范来源为 [RC1 §7 5xx／无法解析预期 JSON 行](../brief/P3_specification_v1.0-rc1.md) 与 [RC2 §7 同行](../brief/P3_specification_v1.0-rc2.md)。RC1 记载停止提议，RC2 记载沿用 RC1 并标记 RESPONSE_ERROR。两版未给出累计 N 次阈值。正式停止语义及适用版本待负责人确认。本附录仅提供来源定位。
