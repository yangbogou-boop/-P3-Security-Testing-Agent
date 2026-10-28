# P3 Spec + Harness Pack 映射索引

日期：2026-10-28。状态：文档候选，待人工审核。核对基线：main，`620a357bfb6c6286c10772498d3c96116703e06c`，开始时工作区和暂存区干净。本轮只整理第二章材料，没有执行测试、实验或新增人工审批。

## 课程适用范围

依据《AI原生工程实践课程_章节02_Intent_Specification与双层Harness_课堂教学PPT_V1.1_20260830-D9 MacPro (1).pptx》第 75 页的章节综合任务；原任务明确使用 PaperManagement-Lab。第 76 页列质量红线，第 78、81 页强调内容而非模板文件名。下表评价功能等价材料，不将案例文件名或 5—8 张任务卡自动认定为 P3 正式评分契约。**整套清单迁移至 P3 的适用范围为 NEEDS_TEACHER_CONFIRMATION**；一般工程文档整理不以此为前置审批。

“完整”仅指对应文档信息，不代表功能或正式课程验收完成。新增材料均待负责人审核；历史报告是解释性来源，不能替代运行证据和批准原件。

## 12 项映射

| 项 | 课程要求 | 对应材料与证据链接 | 文档完整度／具体缺口 | 教师确认 |
| --- | --- | --- | --- | --- |
| 1 | Problem Frame | [问题框架](../brief/P3_problem_frame.md)、[需求阶段总结](P3_requirements_summary.md) | 已有目标、用户、边界；不重复生成 | 清单适用范围待确认 |
| 2 | 稳定 ID Specification | [RC2](../brief/P3_specification_v1.0-rc2.md) | 22 项稳定需求已有；正式课程契约审批未由本文补足 | 正式契约按既有治理 |
| 3 | Acceptance Matrix | [GWT](../eval/P3_GWT_scenarios.md)、[需求追踪](../eval/P3_requirement_traceability.md)、[任务卡](P3_development_task_cards.md) | PARTIAL：方法和任务关联已有；逐项执行版本与可访问原始证据归档仍待补，真实 HTTP 待授权 | 正式验收规则待确认 |
| 4 | State Model | [RC2 §5、7](../brief/P3_specification_v1.0-rc2.md)、[HTTP 设计](../design/P3_http_integration_design.md)、[生命周期](../design/P3_supervisor_lifecycle.md) | 已有产品和监督者状态；无需另造状态模型 | 清单适用范围待确认 |
| 5 | Impact Map | [HTTP 设计](../design/P3_http_integration_design.md)、[ADR-002](../design/ADR_002_black_box_api_scope.md)、[Harness 影响边界](../docs/P3_project_harness.md) | 最小入口已补：模块、格式、旧入口及恢复边界；未来变更仍须逐次评估，不声称覆盖所有迁移 | 清单适用范围待确认 |
| 6 | ADR | [架构总结及 ADR 入口](P3_architecture_summary.md)、[ADR-005](../design/ADR_005_deterministic_strategy_comparison.md) | 001—004 Accepted；005 Proposed；不改决策状态 | 技术决定不需额外教师审批；课程事项另计 |
| 7 | Plan | [七项任务及检查点](P3_development_task_cards.md) | 历史里程碑补录和后续顺序已整理；不是事前计划证据 | 正式阶段映射待确认 |
| 8 | Task Cards | [TC-01～07](P3_development_task_cards.md) | 字段已补；实际责任归属尚待确认，未完成范围明确保留 | 数量／格式适用范围待确认 |
| 9 | Repository Map | [README 目录及阶段入口](../README.md)、本索引、[Harness 权威入口](../docs/P3_project_harness.md) | 最小知识入口已有；本索引解释历史版本，不改写原文 | 清单适用范围待确认 |
| 10 | Harness Manifest | [Project Harness](../docs/P3_project_harness.md)、[离线交付](../docs/P3_offline_delivery.md) | 开发规则说明已补；不是已部署的工具 ACL，发现阶段网络保护尚无本仓库统一入口证明 | 清单适用范围待确认；不新增一般技术审批 |
| 11 | AI 使用披露 | [披露与责任登记](P3_ai_usage_and_responsibility.md) | PARTIAL：可支持的辅助范围已整理；完整调用记录、个人操作和逐文件归属未核验 | 课程披露格式待确认 |
| 12 | 未解决问题 | [RC2 §9](../brief/P3_specification_v1.0-rc2.md)、[治理 A/B/C](../brief/P3_decision_governance.md)、[责任登记](P3_ai_usage_and_responsibility.md) | 阻断范围、建议角色和验证时点已补；责任人 PENDING_OWNER_CONFIRMATION | 仅既有 A 类及课程映射需确认 |

## 当前状态与历史阅读规则

- 当前基线的既有 [CI Run 40642916025](https://github.com/yangbogou-boop/-P3-Security-Testing-Agent/actions/runs/40642916025) 已由前轮只读审计核实为 278 项通过。本轮不复跑，不把 CI 当作正式验收。
- [阶段覆盖表](P3_stage_report_coverage.md)及三份阶段总结保留历史日期和五个关键链接。需求追踪顶部的 258 指 C-3C，不是当前总数；RC2 的早期实现清单和 OQ 原状态按历史时间阅读，活动规范强度不变。
- [14 项真实 HTTP 状态](../eval/P3_http_integration_status.json)保持 PENDING_AUTHORIZATION；未派发独立证明 UNAVAILABLE；C-3D 是可信 Python 宿主的内存模拟，RESPONSE_SENT 不证明 OS 发送。
- 第三章逐项证据卡、第四章成本补测及伙伴复现不在本轮执行范围。不得借文档补录伪造事前约定、执行结果或签署。
