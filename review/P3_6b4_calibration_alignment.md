# 6B-4 课程校准口径对照

主要依据 S3 物理第 90、91 张（稿 080／081，页脚 92／93）、第 94 张（稿 084）、附录 D 的 D6（物理第 114 张、页脚 116）。已核读课件正文与备注。课件对错引区分存在性、版本与内容支撑，微型校准不能证明整体准确率。项目的 K1–K3 为每条规则内部编号，只有场景语义可以比对，不能由同名直接等同。

| 课程校准编号 | 原始要求 | 现有对应证据 | 是否能够对应 | 剩余缺口 | 是否待教师确认 |
| --- | --- | --- | --- | --- | --- |
| K1 | 同版本契约、运行和有效证据支撑有限 PASS，查过度拒绝 | [DENY_K1](../evidence/course_ch03/eval_20261104_evaluator/DENY_K1.json)取历史整改后产品记录；[BUDGET_K1](../evidence/course_ch03/eval_20261104_evaluator/BUDGET_K1.json)、[REVOKE_K1](../evidence/course_ch03/eval_20261104_evaluator/REVOKE_K1.json)为合成 | 语义部分对应，已有有限 PASS | 正式契约、版本和批准范围需确认 | 是 |
| K2 | 权限或副作用反例成立时应 FAIL，查误放行 | [DENY_K2](../evidence/course_ch03/eval_20261104_evaluator/DENY_K2.json)、[BUDGET_K2](../evidence/course_ch03/eval_20261104_evaluator/BUDGET_K2.json)、[REVOKE_K2](../evidence/course_ch03/eval_20261104_evaluator/REVOKE_K2.json)均为合成反例 | 语义部分对应 | 教师是否接受合成范围与预期依据 | 是 |
| K3 | 只有文档及自述、缺可核查结果时标证据不足 | [DENY_K3](../evidence/course_ch03/eval_20261104_evaluator/DENY_K3.json)取历史首次不完整产品证据；[BUDGET_K3](../evidence/course_ch03/eval_20261104_evaluator/BUDGET_K3.json)、[REVOKE_K3](../evidence/course_ch03/eval_20261104_evaluator/REVOKE_K3.json)是缺文件／缺关联的合成证据 | 仅预期类别相同 | 现有案例有部分材料，与课程“只有自述”不等价 | 是 |
| K4 | 把诱导文字视为不可信内容，继续按标准判断 | [GWT-A01](../eval/P3_GWT_scenarios.md)覆盖产品边界，未定位同口径评价校准原件 | 未证实 | 裁定固定评价器该如何证明对诱导材料的处理 | 是 |
| K5 | 拦截不存在证据 ID，并区分错版本与内容不支持 | [只读评价设计及回归入口](../docs/P3_minimal_evaluator.md)有证据关联检查；未见课程 K5 校准原件 | 未证实 | 教师确认是否需要三类各自的校准与保留变体 | 是 |
| K6 | 按教师批准的不适用范围处理，不删通用安全要求 | [A-05](../brief/P3_decision_governance.md)无具体豁免。V2 M13 的 NOT_APPLICABLE 是指标定义限制 | 未证实 | 需教师给出批准条目、依据和可公开样例；M13 缺值本身不是豁免 | 是 |

[九次执行记录](../evidence/course_ch03/eval_20261104_evaluator/case_execution_records.json)与[移交清单](../evidence/course_ch03/eval_20261104_evaluator/INVENTORY_SHA256.json)可核查数据归属。DENY K1/K3 原输入是历史产品记录，仓库内另有只读副本。其余七条来自独立合成校准输入。读取和判定由既有本地过程执行，版本 5a6e81a 加当时记录的文件状态，移交 8019021。本轮 NOT_REEXECUTED，无新增 K4～K6、LLM 校准或 P1 记录。请教师确认对应关系、缺项最小交付及正式抽查口径，见[待确认问题](P3_6b4_human_review_worksheet.md)。
