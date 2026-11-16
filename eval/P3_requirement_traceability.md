# P3 需求—设计—实现—验证—证据追踪

导航更新：2026-11-16，读取基线 `28295838ec7e5324b9eb2ff2d7c8c0fba2b5c744`。返回[项目总索引](../docs/INDEX.md)。本页补充三条任务链，保留原有 22 项需求、GWT 和阶段追踪；不改变需求强度，不以文档存在替代执行或批准。

## 历史数量与当前阅读范围

**258 项无网络测试、12 种重置竞争时序属于 C-3C 阶段历史结果，不是当前全部测试总量。** 来源为[监督审核报告](../review/P3_c3_supervisor_review.md)2026-10-22 当前交付状态及末尾“最终定点修复”；报告起始基线为 `3199b3f9a447cc15548523c995548f139cf8bc18`，后续带工作区修复，不能将最终258项结果直接绑定为该提交原样执行。历史日志已于2026-11-16归档仓库内，位置与逐件摘要见[证据索引](P3_experiment_evidence_index.md#阶段数量与访问边界)。本轮不重跑测试，也不补推当前总量。

## 任务链 A：授权拒绝

| 环节 | 可追踪位置与核对内容 | 状态／限制 |
|---|---|---|
| 需求 | [RC2](../brief/P3_specification_v1.0-rc2.md) P3-REQ-007／008／014～017；[GWT](P3_GWT_scenarios.md) N03／A02；[授权边界](../brief/P3_authorization_boundary.md) | 独立授权、非法候选拒绝及审计要求；不是测试结果 |
| 设计约束 | [ADR-001](../design/ADR_001_controller_split.md)当前澄清、[ADR-004](../design/ADR_004_http_dispatch_and_cancellation.md)、[HTTP 接入](../design/P3_http_integration_design.md)、[离线宿主](../design/P3_c3d_trusted_host_integration.md) | Planner不能授予执行权；同进程模块分离不等于物理隔离 |
| 实现 | [Controller](../src/p3_core/controller.py)、[HTTP 模型](../src/p3_core/http/machine.py)的 `NOT_APPROVED_CANDIDATE`；[审计](../src/p3_core/http/audit.py) | 区分原离线Controller与受控HTTP模型，不从代码存在推定真实HTTP执行 |
| 验证方法 | [证据契约测试](../tests/test_host_evidence_contract.py) `test_denied_candidate_has_linked_audit_but_no_dispatch`；[评价器测试](../tests/test_evaluator.py) `test_k1_historical_pass`；基础回归见[test_core.py](../tests/test_core.py) | 方法/测试定义；本轮未执行，历史执行结果需读下一行 |
| 实际证据 | [第三章评价卡](P3_evaluation_observability_card.md)第G节与[两批原件入口](P3_experiment_evidence_index.md#仓库内实验与原件)；修复后R01为 `run_ce4b0027ae024f05a72d81173c9f05e2` | 历史报告DENY／NOT_EXECUTED、无目标action；首次失败保留。第二批版本为基线加修复差异，非原样HEAD |
| 当前状态 | [HTTP状态](P3_http_integration_status.json)、[课程复核](../review/P3_course_delivery_index.md) | 有限离线拒绝证据可查；独立OS未派发证明、来源认证、真实HTTP及正式验收未由此建立 |

## 任务链 B：Fixed／Dynamic

| 环节 | 可追踪位置与核对内容 | 状态／限制 |
|---|---|---|
| 需求与策略设计 | [RC2](../brief/P3_specification_v1.0-rc2.md) P3-REQ-003／020／021；[ADR-005](../design/ADR_005_deterministic_strategy_comparison.md)、[正式接受记录](../review/P3_adr005_acceptance_20261116.md) | ADR-005 已于2026-11-16有限范围Accepted（仅离线模拟基线）；需求强度不变，正式验收另见下方限制 |
| 实现与验证方法 | [strategies.py](../src/p3_core/http/strategies.py) `FixedSelection`／`EvidenceSelection`；[experiments.py](../src/p3_core/experiments.py)；[策略测试](../tests/test_remaining.py) `test_strategy_repeatable`／`test_strategy_evidence_changes_next_choice`／`test_comparison_records_actual_observations` | 确定性对照策略；测试定义不等于本轮运行 |
| 对照与结果分析 | [工程实验](P3_engineering_experiment.md)、[36次汇总](P3_offline_strategy_results.json)、[归档批次](P3_experiment_evidence_index.md#仓库内实验与原件) | 分析支持有限离线比较，不是独立评价器输出；含异常停止，历史执行版本NOT_FULLY_BOUND |
| 历史用户决定 | [2026-11-16来源摘录](../review/P3_fixed_decision_source_excerpt_20261116.md)、[核验记录](../review/P3_fixed_decision_verification_20261116.md) | 2026-11-09用户决定暂时保留Fixed默认，Dynamic继续对照；历史消息有直接依据，损坏原件未恢复。2026-11-16负责人已接受归档及其限制，同日于[正式接受记录](../review/P3_adr005_acceptance_20261116.md)确认ADR-005有限范围接受 |
| 当前策略与重评 | [delivery.py](../src/p3_core/delivery.py)默认fixed；上述摘录中的“重新评估条件”及[ADR-005 Reconsideration](../design/ADR_005_deterministic_strategy_comparison.md#reconsideration) | 更复杂检查依赖、可信运行/人工成本数据或可复现收益出现时重评；不永久否定Dynamic，不据此授予网络许可 |

实验报告中“负责人仍需确认取舍”是原记录措辞；2026-11-16 ADR-005 已在有限范围（仅离线模拟基线）正式接受，见[正式接受记录](../review/P3_adr005_acceptance_20261116.md)。C-02 未全部完成、REQ-021 正式验收未完成、36次执行版本仍为 `NOT_FULLY_BOUND`，这些限制不因接受而消失。

## 任务链 C：评价 Agent

| 环节 | 可追踪位置与核对内容 | 状态／限制 |
|---|---|---|
| 评价目标 | [评价手册](../docs/P3_minimal_evaluator.md)：DENY对应REQ-007／008／014～017，BUDGET对应REQ-010，REVOKE对应REQ-011；需求定义仍以[RC2](../brief/P3_specification_v1.0-rc2.md)为准 | 仅各需求的有限记录子场景，不另造完整验收要求 |
| 只读设计 | [规则范围与可信边界](../docs/P3_minimal_evaluator.md)、[开发规则](../AGENTS.md) | 仅读既有三文件；不生成产品计划、取得许可、触发检查或修改报告 |
| 实现 | [evaluator.py](../src/p3_core/evaluator.py) `inspect`／`inspect_budget`／`inspect_revoke`／`evaluate`／`evaluate_all` | 实现存在，不自动证明运行成功或人工批准 |
| 校准与复核方法 | [test_evaluator.py](../tests/test_evaluator.py)各规则K1／K2／K3；[手册独立校准](../docs/P3_minimal_evaluator.md#独立校准与回归) | 区分历史产品输入与SYNTHETIC_CALIBRATION；本轮不运行 |
| 历史输出 | [仓库内评价输出归档](../evidence/course_ch03/eval_20261104_evaluator/README.md)（2026-11-04九次单规则及综合展示）与[兼容性归档](../evidence/course_ch03/eval_20261111_compat/INVENTORY_SHA256.json)（2026-11-11）；索引见[评价输出归档](P3_experiment_evidence_index.md#评价与兼容性输出归档) | 已按字节移交，逐件SHA-256可核；产品report仅是输入，不是评价结论；candidate不是第二次独立产品复现；human_signoff仍pending |
| 当前状态 | [课程评价复核](../review/P3_course_delivery_index.md#人工复核与未完成事项) | 规则存在、历史执行完成、输出可复核分别有材料；human_signoff仍pending，overall_verdict=null，不等于人工批准或整体安全PASS |

## 历史追踪正文（2026-10-19起）

以下按原阶段保留；其中“本轮”“当前”和各测试数量仅对应其历史时点，不能覆盖上面的导航更新或升级为本轮验证结果。本节（含下方需求表与各轮补充）中“ADR-005 仍 Proposed”等表述同样只对应其撰写时点；当前状态以 [ADR-005](../design/ADR_005_deterministic_strategy_comparison.md) 与[正式接受记录](../review/P3_adr005_acceptance_20261116.md)为准。

## C-3C 增量（2026-10-21）

基线 182 项保留，新增 [test_c3_supervisor.py](../tests/test_c3_supervisor.py) 35 项，本地共 217 项无网络测试通过。原表和历史数量保留，不表示正式 GWT／HTTP 验收通过。

| 稳定需求 | 新增离线覆盖 | 限制 |
| --- | --- | --- |
| P3-REQ-001、002、007、008、009 | 只读预检、来源未核验、材料冲突、旧 run／generation／实例拒绝 | 不生成真实许可，LocalRegistry 不变 |
| P3-REQ-010、011、012 | 双端撤权顺序、幂等、清理超时／失败、审计中禁止重置、并发重置 | 三计数与 RC2 不改；OS 延迟未测 |
| P3-REQ-014、015、016、017 | 服务摘要不覆盖、关联失败／缺失／重复、部分发送未知、独立 sidecar 哈希、敏感字符串拒绝 | 不生成确认性真实安全结论 |
| P3-REQ-018、019 | 清理后准备新夹具、只读 CLI、14 项管理状态 | 新夹具不继承执行权；网络入口未增加 |

REQ-013 实际响应证据和 REQ-021 真实策略比较仍待授权。见 [机器清单](P3_c3_acceptance_manifest.json)、[生命周期设计](../design/P3_supervisor_lifecycle.md) 和 [本轮报告](../review/P3_c3_supervisor_review.md)。

[RC2](../brief/P3_specification_v1.0-rc2.md) 为规范基线；本表不修改 ID 或强度。没有真实 HTTP 或正式课程验收通过声明。158 项为本地无网络测试数量，并非 158 个 GWT 全项通过。

| 稳定 ID | 强度 | 原 GWT | 当前实现／验证状态 | 可定位自动化测试 |
| --- | --- | --- | --- | --- |
| P3-REQ-001 | MUST | GWT-N01 | 离线子场景通过；真实集成待授权 | `test_preflight_fail_has_no_plan_or_io` |
| P3-REQ-002 | MUST | GWT-P01、GWT-A02 | 离线子场景通过；真实集成待授权 | `test_synthetic_permission_cannot_start_live_run` |
| P3-REQ-003 | MUST | GWT-P04、GWT-P05 | 离线子场景通过；真实集成待授权 | `test_strategy_repeatable / test_strategy_evidence_changes_next_choice` |
| P3-REQ-004 | MUST | GWT-P02、GWT-N02 | 离线子场景通过；真实集成待授权 | `test_three_defects_both_strategies` |
| P3-REQ-005 | MUST | GWT-P02、GWT-N02 | 离线子场景通过；真实集成待授权 | `test_three_defects_both_strategies` |
| P3-REQ-006 | MUST | GWT-P02、GWT-N02 | 离线子场景通过；真实集成待授权 | `test_three_defects_both_strategies` |
| P3-REQ-007 | MUST | GWT-A01、GWT-A02 | 离线子场景通过；真实集成待授权 | `test_bad_selector_fails_closed / test_transport_constructor_has_no_io_and_requires_current_object` |
| P3-REQ-008 | MUST | GWT-N03 | 离线子场景通过；真实集成待授权 | `test_adapter_rejects_header_and_target_mutations` |
| P3-REQ-009 | MUST | GWT-A01 | 离线子场景通过；真实集成待授权 | `test_late_response_during_read_cannot_upgrade` |
| P3-REQ-010 | MUST | GWT-N04、GWT-N05、GWT-A01 | 离线子场景通过；真实集成待授权 | `test_denials_consume_budget_and_eighth_ninth_boundary / test_gwt_a01_a_repeat_stops_only_exhausted_valuable_work` |
| P3-REQ-011 | MUST | GWT-A03 | 离线子场景通过；真实集成待授权 | `test_t28_send_return_and_count_are_one_gate_transaction / test_partial_send_then_revocation_retains_one_model_send` |
| P3-REQ-012 | MUST | GWT-N01、GWT-N05、GWT-N06 | 离线子场景通过；真实集成待授权 | `test_faults_do_not_confirm_leaks / test_audit_capacity_fails_closed` |
| P3-REQ-013 | MUST | GWT-P01、GWT-N06 | 静态传输组件＋假 socket 测试；真实请求／响应未执行 | `test_transport_methods_with_fake_socket_only` |
| P3-REQ-014 | MUST | GWT-P01、GWT-P02、GWT-N02、GWT-N07 | 离线子场景通过；真实集成待授权 | `test_disk_evidence_integrity_and_no_tokens / test_header_timeout_model_never_claims_actual_execution` |
| P3-REQ-015 | MUST | GWT-P03、GWT-N03、GWT-A03 | 离线子场景通过；真实集成待授权 | `test_unique_ids_and_no_overwrite / test_report_tamper_rejected` |
| P3-REQ-016 | MUST | GWT-P03、GWT-N07 | 离线子场景通过；真实集成待授权 | `test_artifacts_never_contain_credentials_parameters_or_exception_body` |
| P3-REQ-017 | MUST | GWT-N04、GWT-N07、GWT-A03 | 离线子场景通过；真实集成待授权 | `test_faults_do_not_confirm_leaks` |
| P3-REQ-018 | MUST | GWT-P02、GWT-N02、GWT-P04 | 离线子场景通过；真实集成待授权 | `test_entire_declared_matrix_and_single_defect_isolation` |
| P3-REQ-019 | SHOULD | GWT-P04、GWT-N01 | 离线子场景通过；真实集成待授权 | `test_cli_validate_does_not_grant_permission / test_cli_network_plan_pending` |
| P3-REQ-020 | MUST | GWT-P04 | 离线子场景通过；真实集成待授权 | `test_comparison_records_actual_observations` |
| P3-REQ-021 | MUST | GWT-P05 | 36 次离线比较完成；ADR Proposed，真实比较／正式验收待办 | `test_comparison_records_actual_observations` |
| P3-REQ-022 | MAY | GWT-A04（后续） | 未实施，保持可选 | 未接入（MAY） |

## 证据定位与限制

- 原离线控制测试：[test_core.py](../tests/test_core.py)，49 项；无网络 HTTP：[test_http_core.py](../tests/test_http_core.py)，54 项；业务夹具：[test_mock_api.py](../tests/test_mock_api.py)，24 项。
- 本轮 [test_remaining.py](../tests/test_remaining.py)，31 项；测试均阻断真实 socket，低层传输测试只用 FakeSocket，未构造真实许可并派发。
- 策略逐次记录：[P3_offline_strategy_results.json](P3_offline_strategy_results.json)，36 个独立 run_id；每条包含逻辑实验口径、三计数／模型计数、分子分母、故障和时间。run_id 对应独立交付包中的 JSONL／Manifest／报告。
- HTTP-T27～T35 的原确定性测试继续通过；新增分段发送、恢复 unknown、响应头／正文区分、绑定错误凭据及证据篡改检查。没有将无网络子场景升级为真实 HTTP-T 验收。
- GWT-A01-a/b/c 保留原测试；动态策略对 MISSING_CONTROL 优先补必要对照，不提前停止正常检查。
- [C-3 清单](P3_http_integration_status.json) 全部真实网络场景为 PENDING_AUTHORIZATION。REQ-013、真实撤权／超时资源回收、REQ-021 实际成本及正式验收未完成。
- 没有真实 LLM 或 Token 用量；准备和人工复核时间未测。模型 FAIL 只表示合成夹具判定，不是现实漏洞报告。

## C-3A/B 离线加固补充（基线 30c98db）

新增 [test_c3_preflight.py](../tests/test_c3_preflight.py) 24 项，本地共 182 项通过；上面的 158 项为前轮基线，不删除或替代原有测试。REQ-007／009／011／012：服务端非阻塞发送与撤权共用短 gate，等待及关闭在门外；REQ-010／015：正发送计数 hook、部分发送、预算到点与恢复记录仍由原控制规则约束；REQ-014／016／017：审计失败、错误绑定、最小摘要和关闭失败明确呈现，不新增确认性安全结论。

服务端新增确定性用例覆盖撤权先／后赢、等待不阻塞撤权、部分发送、到期／超时、旧凭据、错实例与清理失败。真实分支计数 hook 的内存插桩不生成持久化 Evidence，不声称真实请求发生。全部实际 HTTP 场景仍待授权，见 [许可核验与 14 项验收卡](P3_c3_authorization_checklist.md) 和 [本轮审核报告](../review/P3_c3_preflight_review.md)。未变更 RC2 ID／强度，ADR-005 仍 Proposed。
