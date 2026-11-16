# P3 课程交付与人工复核索引

更新：2026-11-16。返回[项目总索引](../docs/INDEX.md)。本页按课程材料与复核任务导航，不替代正式规格、工程决策、真实执行记录或教师验收；章节要求及适用性仍按[治理登记](../brief/P3_decision_governance.md)和各原记录核验。

## 按章节与任务查找

| 章节／任务 | 交付材料与工程依据 | 证据及复核入口 | 已记录状态／待完成事项 |
|---|---|---|---|
| 第一章：GWT与阅读测试 | [GWT作业](P3_course_ch01_GWT.md)、[AI阅读试验](P3_course_ch01_AI_reading_test.md)；[RC2](../brief/P3_specification_v1.0-rc2.md) | 阅读试验保存负责人提供的回答、判断、日期及输入哈希；授权拒绝另走[追踪A](../eval/P3_requirement_traceability.md#任务链-a授权拒绝) | 阅读试验记录为COMPLETED_OWNER_REPORTED_PASS，绑定当时旧AGENTS版本；不沿用于当前文件。课程提交回执仍待补，不把本轮AI查找冒充陌生读者试验 |
| 第二章：Spec＋Harness | [12项Pack映射](P3_spec_harness_pack_index.md)、[10项内容完整性核查](P3_ch02_completeness_check.md)、[任务卡](P3_development_task_cards.md) | [需求追踪](../eval/P3_requirement_traceability.md)、[设计与ADR](../design/README.md)、[AI责任](P3_ai_usage_and_responsibility.md) | 两表口径不同，沿用原职责；课程清单适用性、同行审查、责任归属及正式契约状态按原记录，不能由材料存在推定通过 |
| 第三章：Evaluation与Observability／授权控制 | [评价卡](../eval/P3_evaluation_observability_card.md)、[授权边界](../brief/P3_authorization_boundary.md) | [两次运行与R01原件](../eval/P3_experiment_evidence_index.md#仓库内实验与原件)、[追踪A](../eval/P3_requirement_traceability.md#任务链-a授权拒绝) | 首次FAIL与修复后有限PASS均保留；版本含当次工作区差异。不是OS未发送、完整安全验收或人工批准 |
| 第四章：策略对照与个人工程取舍 | [实验分析](../eval/P3_engineering_experiment.md)、[ADR-005](../design/ADR_005_deterministic_strategy_comparison.md)、[追踪B](../eval/P3_requirement_traceability.md#任务链-bfixeddynamic) | [36次归档](../evidence/course_ch04/strategy_history_36/README.md)、[用户消息摘录](P3_fixed_decision_source_excerpt_20261116.md)、[来源核验](P3_fixed_decision_verification_20261116.md)、[伙伴复现指南](P3_peer_reproduction_guide.md) | 2026-11-09暂时保留Fixed，Dynamic继续对照并保留重评条件；2026-11-16重新归档有直接历史消息依据，损坏原件未恢复，新归档仍待用户最终复核；ADR-005仍Proposed |
| 评价Agent实际展示与校准 | [评价手册](../docs/P3_minimal_evaluator.md)、[实现](../src/p3_core/evaluator.py)、[校准测试](../tests/test_evaluator.py) | [追踪C](../eval/P3_requirement_traceability.md#任务链-c评价-agent)、[仓库内历史输出归档](../eval/P3_experiment_evidence_index.md#评价与兼容性输出归档) | 2026-11-16已将11月4日九次单规则、bundle展示及11月11日兼容性记录按字节移交仓库内；human_signoff=pending，不能由退出码0判定全部PASS |
| 参考自评与责任披露 | [自评手册](../docs/P3_self_assessment.md)、[AI使用与责任](P3_ai_usage_and_responsibility.md) | 冻结Rubric与证据输入按手册定位；个人项须真实人工依据 | 自评分不是课程成绩；本轮不更新分数、不代签、不冒充P1复现 |

## 人工复核与未完成事项

| 类别 | 需要核对或补足的内容 | 当前边界 |
|---|---|---|
| 历史决定与归档复核 | 负责人最终复核[Fixed摘录及核验](P3_fixed_decision_verification_20261116.md)，确认来源和交付范围 | 有直接历史用户消息，不是损坏原件恢复，不认证独立签名或本人实验经历 |
| 正式批准 | ADR-005正式接受、课程材料审核/回执及需教师确认的契约适用性 | 均不因本轮索引更新自动完成；其他ADR当前状态以正文为准 |
| 证据缺口 | 36次历史执行版本NOT_FULLY_BOUND、历史人工成本未测、独立OS未派发证明UNAVAILABLE | 不推算、不重造、不将归档提交当执行版本 |
| 证据已移交，来源仍私有 | [证据索引](../eval/P3_experiment_evidence_index.md)登记的评价展示、兼容性结果和C-3C日志已按字节复制入仓库内 | 原件仍在私有来源目录；版本绑定与人工批准仍未完成，逐件摘要见各目录`INVENTORY_SHA256.json` |
| 伙伴与本人核查 | 按[伙伴指南](P3_peer_reproduction_guide.md)、章节原记录和评价展示的复核要求分别保留真实过程 | AI辅助、本人确认、P1独立活动分别记录；不能从指南/空白表推定已完成 |
| 真实HTTP与总体结论 | [14项状态](../eval/P3_http_integration_status.json)和[授权核验卡](../eval/P3_c3_authorization_checklist.md) | 保持待授权；索引不授予执行权，不宣称整体安全PASS或课程验收完成 |

## 本机仓库外来源与仓库内归档

上述材料的原件仍保存在私有来源目录 `D:\codex\...`（本机绝对路径仅作来源标注，不构造超链接，也不宣称已有公开交付包）。2026-11-16 已按字节复制入仓库：评价展示与校准→[eval_20261104_evaluator](../evidence/course_ch03/eval_20261104_evaluator/README.md)；兼容性输出→[eval_20261111_compat](../evidence/course_ch03/eval_20261111_compat/INVENTORY_SHA256.json)；C-3C日志→[c3c_supervisor_20261022](../evidence/course_ch03/c3c_supervisor_20261022/INVENTORY_SHA256.json)。

该交付目录中的`P3_Ch04_personal_decision_20261109.md`已确认正文损坏，保留原状但不作为完整原文证据；本轮未将其复制入公开仓库。引用当前可读决定应使用本页链接的2026-11-16来源摘录及核验记录。Word/PDF、课程提交快照和回执按教师实际要求另行提供，不以工程Markdown自动替代。

258项仅指C-3C历史阶段，不是当前全部测试总量。此前620个链接检查通过不证明外部交付、跨平台访问、语义正确或人工批准。本页只维护章节路由及明确缺口，不复制各章明细或历史长日志。
