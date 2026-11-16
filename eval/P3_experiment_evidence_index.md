# P3 实验与评价证据索引

更新：2026-11-16。返回[项目总索引](../docs/INDEX.md)，需求/设计/实现的关联见[需求追踪](P3_requirement_traceability.md)。本页只定位批次与记录，不重跑实验，不复制逐次输出。文件存在、可访问、具有可追溯依据、结论经过人工批准分别记录；索引不是批准书。

## 仓库内实验与原件

| 任务／验证目标 | 批次与真实位置 | 证据类型／可访问状态 | 历史结果、限制及人工事项 |
|---|---|---|---|
| 授权拒绝首次执行；REQ-007／008／014～017有限子场景 | `eval_20261028_01`：[事前约定](../evidence/course_ch03/eval_20261028_01/evaluation_agreement.md)、[文件清单](../evidence/course_ch03/eval_20261028_01/file_inventory.json)；客户端 `run_e2b938e432d044e69427e50f2b1a9aaf` 的[事件](../evidence/course_ch03/eval_20261028_01/artifacts/run_e2b938e432d044e69427e50f2b1a9aaf/events.jsonl)、[报告](../evidence/course_ch03/eval_20261028_01/artifacts/run_e2b938e432d044e69427e50f2b1a9aaf/report.json)、[Manifest](../evidence/course_ch03/eval_20261028_01/artifacts/run_e2b938e432d044e69427e50f2b1a9aaf/manifest.json) | 历史离线产品原件；仓库内可读 | [评价卡](P3_evaluation_observability_card.md)记录首次FAIL；缺report_sha256，后续DENY评价为证据不足。失败原件保留，不补写哈希制造通过 |
| 修复后R01授权拒绝；同一有限目标 | `eval_20261028_02`：[约定](../evidence/course_ch03/eval_20261028_02/evaluation_agreement.md)、[文件清单](../evidence/course_ch03/eval_20261028_02/file_inventory.json)；`run_ce4b0027ae024f05a72d81173c9f05e2` 的[事件](../evidence/course_ch03/eval_20261028_02/artifacts/run_ce4b0027ae024f05a72d81173c9f05e2/events.jsonl)、[报告](../evidence/course_ch03/eval_20261028_02/artifacts/run_ce4b0027ae024f05a72d81173c9f05e2/report.json)、[Manifest](../evidence/course_ch03/eval_20261028_02/artifacts/run_ce4b0027ae024f05a72d81173c9f05e2/manifest.json) | 历史离线产品原件；仓库内可读；是评价输入，不是评价器输出 | [评价卡第G节](P3_evaluation_observability_card.md)记录限定PASS；DENY／NOT_EXECUTED，无目标action；[当次验证JSON](../evidence/course_ch03/eval_20261028_02/verification.json)、[全量日志](../evidence/course_ch03/eval_20261028_02/full_suite_output.txt)。基线67242ba加[修复差异](../evidence/course_ch03/eval_20261028_02/execution_code_diff.patch)及[执行上下文](../evidence/course_ch03/eval_20261028_02/execution_context.json)，不能称原样HEAD；来源认证、OS停发证明及正式验收未建立 |
| Fixed／Dynamic对照；REQ-003／020／021 | 历史36次：[汇总](P3_offline_strategy_results.json)、[实验分析](P3_engineering_experiment.md)、[按Run定位原件](../evidence/course_ch04/strategy_history_36/README.md)、[108文件清单](../evidence/course_ch04/strategy_history_36/archive_manifest.json) | 合成夹具的历史离线运行及事后分析；仓库内可读 | 24次COMPLETED、12次异常STOPPED，不叫36次全通过；执行版本NOT_FULLY_BOUND，归档提交不是执行SHA；人工成本未测，不能证明普遍策略优劣或伙伴已复现 |
| Fixed个人取舍的来源核验 | 历史决定2026-11-09；2026-11-16[消息摘录](../review/P3_fixed_decision_source_excerpt_20261116.md)及[核验报告](../review/P3_fixed_decision_verification_20261116.md) | 历史用户消息的重新归档，不是实验输出；仓库内可读 | 暂时保留Fixed默认，Dynamic继续对照及重评；损坏外部原件未恢复，不作完整原文依据。新归档待用户最终复核；ADR-005仍Proposed |

## 评价与兼容性输出归档

2026-11-16 已将下列本机仓库外材料按字节原样复制入仓库，原件仍保留在私有来源目录。逐件 SHA-256、批次、类别与输入标签见各目录的 `INVENTORY_SHA256.json`（派生移交清单，不是历史执行时生成的原始 Manifest）。源码内原有本机绝对路径作为历史来源标注保留，不构成可移交链接；跨机器读取请使用仓库内相对路径。其中 `unittest.log`、`baseline_unittest.log`、`candidate_unittest.log` 命中仓库 `.gitignore` 的 `*.log`，提交时需 `git add -f`，或经用户批准后调整忽略规则。

| 评价任务／目标 | 批次与仓库内位置 | 已归档的输出及执行依据 | 状态与限制 |
|---|---|---|---|
| DENY／BUDGET／REVOKE及K1／K2／K3校准；目标映射见[任务链C](P3_requirement_traceability.md#任务链-c评价-agent) | 2026-11-04；[eval_20261104_evaluator](../evidence/course_ch03/eval_20261104_evaluator/README.md)、[移交清单](../evidence/course_ch03/eval_20261104_evaluator/INVENTORY_SHA256.json) | `DENY_K1.json`～`DENY_K3.json`、`BUDGET_K1.json`～`BUDGET_K3.json`、`REVOKE_K1.json`～`REVOKE_K3.json`及`.stderr.txt`；`case_execution_records.json`记录调用/退出码；`context_before.json`记录版本；`unittest_result.json`及`unittest.log`记录96项 | 三规则各K1=PASS、K2=FAIL、K3=INSUFFICIENT_EVIDENCE；九次退出码0只表示完成。类别：历史产品输入（HISTORICAL_PRODUCT_RECORD）用于DENY K1/K3，合成校准输入（SYNTHETIC_CALIBRATION）用于其余，不能当真实漏洞或P1结果。96项为该次评价器专项测试，不是本轮或全项目总量；human_signoff仍pending |
| 统一只读评价展示 | 同一2026-11-04批次目录 | `bundle_history_good.json/.txt`、`bundle_history_incomplete.json/.txt`、`bundle_synthetic_revoke_fail.json/.txt`，各自配套`*_execution.json`；输入位置见[映射](../evidence/course_ch03/eval_20261104_evaluator/historical_reference_map.json)及`calibration_inputs/` | 历史Good输入是修复后R01；总体结论不生成。合成反例和历史输入分开，文件可读不等于人工批准 |
| 文档整改前后评价兼容性 | 2026-11-11；[eval_20261111_compat](../evidence/course_ch03/eval_20261111_compat/INVENTORY_SHA256.json) | [baseline_compatibility.json](../evidence/course_ch03/eval_20261111_compat/baseline_compatibility.json)、[candidate_compatibility.json](../evidence/course_ch03/eval_20261111_compat/candidate_compatibility.json)的`evaluator_output`字段；[compatibility.py](../evidence/course_ch03/eval_20261111_compat/compatibility.py)、[compatibility_result.txt](../evidence/course_ch03/eval_20261111_compat/compatibility_result.txt) | 两版均对**同一 baseline 产品输入副本**（R01 `run_ce4b0027ae024f05a72d81173c9f05e2`）评价：DENY/BUDGET=PASS，REVOKE=INSUFFICIENT_EVIDENCE，CONSISTENT_READS、overall_verdict=null、human_signoff=pending。candidate文件名不是另一产品run，也不是两次独立复现；未包含baseline/candidate整树与baseline.zip |

11月11日两份兼容性文件的SHA-256：baseline为`79c5ff0e4ece31c75b17e21c466286b2a2b53f391ab45e5cb11b8ee1d08daed2`；candidate为`bf706f0f4a5e629673845247c06a235df6e636ae5e33e701d9c07cb3618229bb`。仅用于识别现有字节，不是来源认证。移交已一并保存输入映射、脚本和版本记录，不只交摘要截图。

独立复核先读[评价手册](../docs/P3_minimal_evaluator.md)，再区分规则结论、证据引用、来源标记和人工签署；实现见[evaluator.py](../src/p3_core/evaluator.py)，校准定义见[test_evaluator.py](../tests/test_evaluator.py)。本轮只读取历史输出，没有运行评价器或重新制造证据。

## 阶段数量与访问边界

- C-3C的258项测试、12种重置竞争时序是2026-10-22[监督审核报告](../review/P3_c3_supervisor_review.md)的历史结果，不代表当前全部测试总量。报告起始基线3199b3f，最终带工作区增量；执行身份应结合原差异/哈希，不能从报告日期推定唯一原样提交。
- 原日志目录为`D:\codex\2026-10-12\referenced-chatgpt-conversation-this-is-an\outputs\c3-supervisor`（私有来源，原件保留）。2026-11-16 已将同批23个历史文件按字节复制入[c3c_supervisor_20261022](../evidence/course_ch03/c3c_supervisor_20261022/INVENTORY_SHA256.json)：`unittest-final.txt`末尾为258项、OK；`registration-reset-races.json`、`baseline.json`、`P3-c3-supervisor-review.diff`等均在，作为版本/竞争时序材料。执行版本为 `3199b3f + 当时工作区增量`，不是当前HEAD重新执行；本轮没有重放12时序或复验历史保护。
- [真实HTTP状态](P3_http_integration_status.json)仍为14项PENDING_AUTHORIZATION；独立未派发证明UNAVAILABLE。历史离线成功、完整性哈希、个人决定均不替代目标许可、教师验收或来源认证。
- 此前620个链接通过仅覆盖当时检查器识别的本地相对链接；本页仓库外路径、跨平台获取、输出语义和人工批准须分别核验。后续新增批次只登记入口及限制，不复制36次明细或覆盖原件。
