# 6B-4 人工核查工作表

证据基线 `7178dbbb5f3caedca6e7e53cf85a5785d70ecc82`。状态 `PENDING_HUMAN_REVIEW`。人工执行、观察、签署与批准由实际主体回填。工程技术依据见[22 项矩阵](../eval/P3_acceptance_matrix_6b4.md)。

## 负责人逐项核查

填写实际查阅的工件、版本和限制。核查结论可填「接受现有技术证据」「需补资料」「不适用于本次审查并附依据」。课程验收另录教师凭据。

| Requirement ID | 实际证据、版本与限制 | 负责人意见 | 记录人、日期／后续 |
| --- | --- | --- | --- |
| P3-REQ-001 |  | PENDING_HUMAN_REVIEW |  |
| P3-REQ-002 |  | PENDING_HUMAN_REVIEW |  |
| P3-REQ-003 |  | PENDING_HUMAN_REVIEW |  |
| P3-REQ-004 |  | PENDING_HUMAN_REVIEW |  |
| P3-REQ-005 |  | PENDING_HUMAN_REVIEW |  |
| P3-REQ-006 |  | PENDING_HUMAN_REVIEW |  |
| P3-REQ-007 |  | PENDING_HUMAN_REVIEW |  |
| P3-REQ-008 |  | PENDING_HUMAN_REVIEW |  |
| P3-REQ-009 |  | PENDING_HUMAN_REVIEW |  |
| P3-REQ-010 |  | PENDING_HUMAN_REVIEW |  |
| P3-REQ-011 |  | PENDING_HUMAN_REVIEW |  |
| P3-REQ-012 |  | PENDING_HUMAN_REVIEW |  |
| P3-REQ-013 |  | PENDING_HUMAN_REVIEW |  |
| P3-REQ-014 |  | PENDING_HUMAN_REVIEW |  |
| P3-REQ-015 |  | PENDING_HUMAN_REVIEW |  |
| P3-REQ-016 |  | PENDING_HUMAN_REVIEW |  |
| P3-REQ-017 |  | PENDING_HUMAN_REVIEW |  |
| P3-REQ-018 |  | PENDING_HUMAN_REVIEW |  |
| P3-REQ-019 |  | PENDING_HUMAN_REVIEW |  |
| P3-REQ-020 |  | PENDING_HUMAN_REVIEW |  |
| P3-REQ-021 |  | PENDING_HUMAN_REVIEW |  |
| P3-REQ-022 |  | PENDING_HUMAN_REVIEW |  |

## Assumption 责任确认

原始条目来自 [AS-01～05 记录](P3_ai_usage_and_responsibility.md)。建议角色尚未接受分工。负责人应填写实际责任人、验证门槛、完成状态和证据引用。

| Assumption ID | 原始假设 | 当前验证依据 | 建议责任角色 | 建议验证时点 | 负责人确认 | 实际状态 |
| --- | --- | --- | --- | --- | --- | --- |
| AS-01 | 可信 Python 宿主不含任意同进程恶意代码；README／架构说明 | [Harness 适用范围](../docs/P3_project_harness.md)及进程内阻断记录，独立 OS 隔离未验证 | 架构负责人 | 信任域变更或对外主张更强隔离之前 |  | `PENDING_OWNER_CONFIRMATION` |
| AS-02 | 六候选和四模式可代表当前教学切片；HTTP 契约 | [RC2](../brief/P3_specification_v1.0-rc2.md)及旧六项离线契约，仅支持现行教学切片 | 测试负责人 | 扩展场景或提交最终适用范围前 |  | `PENDING_OWNER_CONFIRMATION` |
| AS-03 | 8／90／1 与容量建议适合试跑；RC2／交付说明 | [预算决策 A-02](../brief/P3_decision_governance.md)，当次示例、V2 快照和班级冻结各有用途 | 实验负责人 | 课程正式采用数字预算前 |  | `PENDING_OWNER_CONFIRMATION` |
| AS-04 | README 标准库命令可在伙伴环境复现 | [伙伴复现指南](P3_peer_reproduction_guide.md)，伙伴环境记录尚待提交 | 复现负责人和伙伴 | 伙伴实际选择环境并进行独立复现时 |  | `PENDING_OWNER_CONFIRMATION` |
| AS-05 | 仓库外历史运行与报告所述执行版本一致 | [实验索引](../eval/P3_experiment_evidence_index.md)，36 次逐次执行版本为 NOT_FULLY_BOUND | 证据负责人 | 将历史运行用于版本级或因果论证前 |  | `PENDING_OWNER_CONFIRMATION` |

## AI 使用及责任确认

| 核查项目 | 参考 | 确认人、实际日期及证据或异议 |
| --- | --- | --- |
| AI 辅助范围与完整调用记录的边界 | [披露记录](P3_ai_usage_and_responsibility.md) |  |
| 规格、验收范围、ADR 与正式提交责任 | [治理登记](../brief/P3_decision_governance.md) |  |
| P1 独立执行、D7 签署与教师审批记录的归属 | 本工作表和相应真人记录 |  |
| 课程提交版本、附件、渠道与回执 | [课程交付索引](P3_course_delivery_index.md) |  |

## D7 人工签署空白表

| 项目 | 真人填写 |
| --- | --- |
| 评价人、评价组、被评价组、实际日期 |  |
| 评价对象、契约／规则版本、代码 SHA、运行编号 |  |
| AI 使用范围与引用的原始证据 ID、路径、版本 |  |
| 实际核查方式、观察、分歧、限制及未查范围 |  |
| 人工裁决（接受／不接受／补证据）和适用范围 |  |
| 被评价组回应、整改及二次核查 |  |
| 签署人及签署凭据 |  |
| 教师复核记录（如适用） |  |

签署状态 `PENDING_HUMAN_REVIEW`。依据 S3 附录 D（D7）与 CH03 物理第 43 张（页脚 44）复核后填写。

## P1 待复核事项索引

| 任务 | 首要证据 | P1 待提交 |
| --- | --- | --- |
| T1 第二章规格 | [RC2](../brief/P3_specification_v1.0-rc2.md)、[Spec＋Harness 索引](P3_spec_harness_pack_index.md)、[22 项矩阵](../eval/P3_acceptance_matrix_6b4.md) | 逐条核查及自主发现记录 |
| T2 第三章 R01 | [评价工作表](../eval/P3_evaluation_observability_card.md)、[原证据路径与版本索引](../eval/P3_experiment_evidence_index.md) | 首次与修复后结果分别审阅，记录可核验边界 |
| T3 第四章独立离线复现 | [伙伴复现指南](P3_peer_reproduction_guide.md)、[历史 36 次归档](../evidence/course_ch04/strategy_history_36/README.md) | P1 自己的环境、SHA、实际命令、run_id、输出、限制 |
| T4 V2 工程审查 | [V2 证据协议](../docs/P3_reviewed_evidence_v2.md) 与冻结包 | 证据、权限和撤权的独立复核 |
| T4-A / T4-B 补充复核建议 | [范围绑定方案](P3_reviewed_scope_binding_design_review.md)（711550a）、[指标定义](../docs/P3_reviewed_metrics_v1.md)（7178dbb） | 范围、预算、候选和摘要关联，以及 M1～M13、F1/F2 和缺值语义的独立判断 |

原 P1 冻结包继续以 `103a9ed36a696a9d686ed998a6fa9fd3472fea2c` 为版本。本轮仅整理索引，人工结果 `PENDING_HUMAN_REVIEW`。是否制作增量资料待负责人确认。

## 教师待确认问题

| 事项 | 待教师确认的问题 | 答复与凭据 |
| --- | --- | --- |
| 第二章适用清单 | 10 项内容完整性、12 项 Spec＋Harness Pack 分别如何用于本组？PaperManagement Lab 示例中哪些项目适用？最终材料、格式、渠道和回执要求是什么？ |  |
| A-01 与 A-02 | 本组实际评审范围及获批目录如何记录？示例预算 8／90／1 是否采用，哪一份记录构成正式冻结？ |  |
| A-03 | 正式采用的契约、Rubric、阻断规则、评价输出及保留测试是哪一版？CH03 的有限 R01 证据是否足以作为对应作业的提交材料？ |  |
| D6 校准 | [K1–K6 对照](P3_6b4_calibration_alignment.md)中，课程 K1–K3 与现有合成／历史案例能否对应？K4～K6 各需何种独立材料及抽查变体？ |  |
| A-05 与 D7 | 哪些课程条目可标正式不适用，所需书面凭据与最低证据是什么？D7 由谁签署，如何处理异议和复核？ |  |
| E1、E2、E3 | E1 的独立复现／成本抽查、E2 Change 的发布及复核、E3 高风险复核需提交哪些真人记录？C-02／REQ-021 是否需补额外证据？ |  |
| Harness 与 V2 | 是否需另提交伙伴环境可用性记录或更强隔离证明？GAP-032 与 M7、M10、M12、M13 的证据限制是否影响本次课程验收？ |  |

教师待确认状态 `PENDING_TEACHER_CONFIRMATION`。审批和测试执行的正式门槛见[治理登记](../brief/P3_decision_governance.md)。
