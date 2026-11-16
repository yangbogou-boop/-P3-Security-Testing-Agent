# P3 设计与 ADR 索引

更新：2026-11-16。返回[项目总索引](../docs/INDEX.md)。本页提供设计用途、依据和正文状态的导航；规范以[RC2](../brief/P3_specification_v1.0-rc2.md)、执行边界以[授权边界](../brief/P3_authorization_boundary.md)、审批责任以[治理登记](../brief/P3_decision_governance.md)为准。ADR状态以各正文当前状态段为准，索引不授予执行权或批准。

## ADR 状态概览

| ADR | 正文当前状态 | 主要用途与依据 | 阅读限制 |
|---|---|---|---|
| [001 Planner／Controller分离](ADR_001_controller_split.md) | Accepted，2026-09；含2026-10-12澄清 | 独立授权的历史决策；当前范围读正文第6节及[RC2](../brief/P3_specification_v1.0-rc2.md) | 标题“物理分离”和早期LLM描述不能当当前实现；正文澄清当前不保证物理隔离 |
| [002 黑盒API范围](ADR_002_black_box_api_scope.md) | Accepted，正文当前状态及第6节 | 用户、验收场景、首版黑盒范围；[问题框架](../brief/P3_problem_frame.md) | 首轮Proposed及统一待老师批准措辞属于历史，非当前状态 |
| [003 本地执行与证据](ADR_003_local_execution_and_evidence.md) | Accepted，2026-10-14负责人确认技术方案 | Python标准库、可信配置、JSONL／Manifest和CLI；[离线交付手册](../docs/P3_offline_delivery.md) | 技术路线确认不等于运行许可、容量结论或验收完成 |
| [004 派发与在途撤权](ADR_004_http_dispatch_and_cancellation.md) | Accepted，2026-10-19正文顶部当前Status | 分离状态机与单I/O所有者；[HTTP接入设计](P3_http_integration_design.md) | 下方2026-10-14 Proposed原文保留；不是实际目标许可 |
| [005 Fixed／Dynamic比较](ADR_005_deterministic_strategy_comparison.md) | **Proposed**，2026-10-19 | [第四章实验分析](../eval/P3_engineering_experiment.md)、[36次归档入口](../evidence/course_ch04/strategy_history_36/README.md)、[历史用户决定](../review/P3_fixed_decision_source_excerpt_20261116.md) | 用户暂时保留Fixed的决定，不自动构成正式ADR接受、教师批准或验收 |

## 架构与实现设计

| 文件 | 主要用途 | 正文状态／关联验证 |
|---|---|---|
| [HTTP接入设计](P3_http_integration_design.md) | 请求与响应契约、授权/派发/撤权、审计及迁移边界 | Draft／待审核的历史设计；契约见[草案](../brief/P3_http_contract_draft.md)，验证入口见[需求追踪A](../eval/P3_requirement_traceability.md#任务链-a授权拒绝)及[验收计划](../eval/P3_http_acceptance_plan.md) |
| [C-3C生命周期](P3_supervisor_lifecycle.md) | Supervisor、LifecyclePort、证据协调、重置与清理 | 实现候选、待人工代码审核；258项属于C-3C历史结果，见[阶段证据说明](../eval/P3_experiment_evidence_index.md#阶段数量与访问边界) |
| [C-3D可信宿主集成](P3_c3d_trusted_host_integration.md) | 离线Fixture／Controller／sidecar协调、run绑定与有限报告 | 候选实现、待人工审核，仅OFFLINE_SIMULATION；见[演示计划](../eval/P3_c3d_offline_demo_plan.md)、[实现审核记录](../review/P3_c3d_implementation_review.md) |

## 状态差异与决策依据

- HTTP接入设计仍有“ADR-004 Proposed”等历史措辞，ADR-004正文顶部已经注明Accepted。此为可见时点差异，依正文当前状态阅读；本轮不改历史设计或ADR。
- ADR-005及工程实验报告仍保留等待负责人确认的原措辞。2026-11-09用户决定**暂时保留Fixed为默认，Dynamic继续作为对照**；2026-11-16建立[来源摘录](../review/P3_fixed_decision_source_excerpt_20261116.md)与[核验记录](../review/P3_fixed_decision_verification_20261116.md)。历史决定有直接消息依据，损坏原件未恢复，新归档仍待用户最终复核，ADR-005未正式接受。
- 用户原话的重评条件是更复杂检查依赖、可信实际运行/人工成本数据或可复现Dynamic收益；正式设计的重评门槛另见[ADR-005 Reconsideration](ADR_005_deterministic_strategy_comparison.md#reconsideration)。这些条件不授予真实HTTP执行权。
- [实验与评价索引](../eval/P3_experiment_evidence_index.md)负责批次和原件，[课程索引](../review/P3_course_delivery_index.md)负责交付及人审。文件存在、当前可访问、内容来源可追踪和结论经人工批准须分别判断；Accepted也不等于已实现或已验收。

## 维护

设计新增或状态变化时先核对权威正文再更新本表，保留替代关系和历史时点，不在此复制实验输出或累积轮次日志。本页没有改动ADR状态。链接检查只覆盖实际运行的本地相对路径检查，不证明外部访问、跨平台可移交性或语义正确。
