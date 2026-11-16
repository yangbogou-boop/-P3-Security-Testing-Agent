# P3 项目文档索引

这是仓库级文档入口。课程章节清单、任务卡与证据索引各自服务于其所述范围。

整改前提交为 `eba1e1b7fe584331573aa3348c3b3fa9e89cebd1`。当前工程规格为 V1.0-RC2，交付范围为离线模拟与只读评价。真实 HTTP 的 14 项验收仍为 `PENDING_AUTHORIZATION`，见[状态清单](../eval/P3_http_integration_status.json)。C-3D 独立未派发证明仍为 `UNAVAILABLE`。旧测试数量按记录的阶段和版本阅读。

## 规格与授权（Specification）

- [RC2 工程候选基线](../brief/P3_specification_v1.0-rc2.md)定义需求、计数、终态和证据；[授权边界](../brief/P3_authorization_boundary.md)定义执行条件；[工程治理](../brief/P3_decision_governance.md)说明审批及责任。背景见[问题框架](../brief/P3_problem_frame.md)。
- [HTTP 契约草案](../brief/P3_http_contract_draft.md)描述合成接口、权限矩阵和 schema，离线实现见 [HttpConfig](../src/p3_core/http/contract.py)。
- [RC1](../brief/P3_specification_v1.0-rc1.md)为历史快照，活动要求采用 RC2。正式课程与实际目标许可按治理材料核验。

## 决策（ADR）与架构（Architecture Design）

- Accepted：[001 Planner／Controller 分离](../design/ADR_001_controller_split.md)、[002 黑盒 API 范围](../design/ADR_002_black_box_api_scope.md)、[003 本地执行与证据](../design/ADR_003_local_execution_and_evidence.md)、[004 派发与取消](../design/ADR_004_http_dispatch_and_cancellation.md)。
- Proposed：[005 固定与证据优先策略](../design/ADR_005_deterministic_strategy_comparison.md)，对应[策略实现](../src/p3_core/http/strategies.py)与第四章实验。负责人取舍记录与 ADR 正式状态分别管理。
- 实现参考：[HTTP 接入](../design/P3_http_integration_design.md)、[C-3C 生命周期](../design/P3_supervisor_lifecycle.md)、[C-3D 离线可信宿主](../design/P3_c3d_trusted_host_integration.md)。文中候选、待审核和测试数量按撰写时点解释。

## 开发规则（Harness）与运行手册（Runbook）

- [AGENTS.md](../AGENTS.md)是当前开发规则，含安全约束、模块定位及验证命令。[Project Harness 草案](P3_project_harness.md)解释开发 Agent 与产品权限分工，其中“未发现 AGENTS.md”及 278 项测试属于 2026-10-28 快照。
- [离线交付手册](P3_offline_delivery.md)提供 CLI 参数、退出码、证据、重置与恢复，入口为 [delivery.py](../src/p3_core/delivery.py)。环境为 Python 3.9+ 与标准库。旧 `src/main.py` 及配套目录为历史原型。
- [独立评价手册](P3_minimal_evaluator.md)说明 [evaluator.py](../src/p3_core/evaluator.py)的 DENY、BUDGET、REVOKE 规则与校准。[参考自评手册](P3_self_assessment.md)说明冻结的 `P3-SELF-ASSESSMENT-001 v0.1` 与人工条件。
- [伙伴复现指南](../review/P3_peer_reproduction_guide.md)按版本定位输入与证据。伙伴执行需独立记录。

## 验收与追踪（Evaluation）

| 验证目标 | 规范与评价 | 实现和测试 | 记录 |
|---|---|---|---|
| 需求与场景覆盖 | [GWT](../eval/P3_GWT_scenarios.md)前半为活动场景，末段为旧扫描原型 | [需求追踪](../eval/P3_requirement_traceability.md)包含实现和测试映射 | [早期离线验证](../eval/P3_offline_core_validation.md)、[C-3D 演示计划](../eval/P3_c3d_offline_demo_plan.md)，258 项属于 C-3C |
| 授权拒绝与留痕 | [第三章评价卡](../eval/P3_evaluation_observability_card.md) | [Controller](../src/p3_core/controller.py)、[HTTP 模型](../src/p3_core/http/machine.py)、[证据契约测试](../tests/test_host_evidence_contract.py)、[评价器测试](../tests/test_evaluator.py) | 下文两次运行，保留首次失败与修复后结果 |
| Fixed／Dynamic 比较 | [第四章实验分析](../eval/P3_engineering_experiment.md) | [实验入口](../src/p3_core/experiments.py)、[策略回归](../tests/test_remaining.py) | [36 次历史汇总](../eval/P3_offline_strategy_results.json)、[归档索引](../evidence/course_ch04/strategy_history_36/README.md) |
| HTTP 验收准备 | [验收计划](../eval/P3_http_acceptance_plan.md)、[许可核验卡](../eval/P3_c3_authorization_checklist.md) | [HTTP 核心回归](../tests/test_http_core.py)、[C-3 预检回归](../tests/test_c3_preflight.py) | [真实状态](../eval/P3_http_integration_status.json)，与离线回归分别记录 |

## 原始证据（Evidence）

- 第三章首次执行的[评价约定](../evidence/course_ch03/eval_20261028_01/evaluation_agreement.md)和[原始文件清单](../evidence/course_ch03/eval_20261028_01/file_inventory.json)。
- 修复后执行的[评价约定](../evidence/course_ch03/eval_20261028_02/evaluation_agreement.md)和[原始文件清单](../evidence/course_ch03/eval_20261028_02/file_inventory.json)。R01 的[事件](../evidence/course_ch03/eval_20261028_02/artifacts/run_ce4b0027ae024f05a72d81173c9f05e2/events.jsonl)、[报告](../evidence/course_ch03/eval_20261028_02/artifacts/run_ce4b0027ae024f05a72d81173c9f05e2/report.json)、[Manifest](../evidence/course_ch03/eval_20261028_02/artifacts/run_ce4b0027ae024f05a72d81173c9f05e2/manifest.json)可逐项关联。
- 第四章[108 个原件清单](../evidence/course_ch04/strategy_history_36/archive_manifest.json)。历史执行版本为 `NOT_FULLY_BOUND`，归档提交仅用于定位原件。

## 审查（Review）与历史报告（Historical Report）

- 课程材料：[第一章 GWT](../review/P3_course_ch01_GWT.md)、[阅读测试](../review/P3_course_ch01_AI_reading_test.md)、[第二章 Pack 映射](../review/P3_spec_harness_pack_index.md)、[第二章完整性](../review/P3_ch02_completeness_check.md)。阅读测试按记录中的旧 AGENTS 版本与哈希复核。
- [AI 使用与责任](../review/P3_ai_usage_and_responsibility.md)、[开发任务卡](../review/P3_development_task_cards.md)保留各自的来源与时点。Word/PDF 课程交付格式按教师要求另行处理。
- 历史总览：[阶段覆盖](../review/P3_stage_report_coverage.md)、[需求](../review/P3_requirements_summary.md)、[架构](../review/P3_architecture_summary.md)、[离线工程](../review/P3_offline_engineering_summary.md)。旧 README 的阶段综述可用 `git show eba1e1b:README.md` 查看。
- 阶段审核：[HTTP 设计](../review/P3_http_design_review.md)、[无网核心](../review/P3_http_offline_core_review.md)、[模拟 API](../review/P3_mock_api_c1_review.md)、[后续工程](../review/P3_remaining_development_review.md)、[C-3A/B 预检](../review/P3_c3_preflight_review.md)、[C-3C 监督](../review/P3_c3_supervisor_review.md)、[C-3D 实现](../review/P3_c3d_implementation_review.md)。

## 维护

新增文档按职责登记，状态以其权威来源更新。在仓库根目录运行 `python tools/check_doc_links.py` 检查入口，添加 `--all` 检查 Markdown 的本地相对链接。固定版本外链和机器本地日志按原记录核对。
