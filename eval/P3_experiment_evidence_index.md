# P3 实验与评价证据索引

更新：2026-11-16。返回[项目总索引](../docs/INDEX.md)，需求/设计/实现的关联见[需求追踪](P3_requirement_traceability.md)。本页只定位批次与记录，不重跑实验，不复制逐次输出。文件存在、可访问、具有可追溯依据、结论经过人工批准分别记录；索引不是批准书。

## 仓库内实验与原件

| 任务／验证目标 | 批次与真实位置 | 证据类型／可访问状态 | 历史结果、限制及人工事项 |
|---|---|---|---|
| 授权拒绝首次执行；REQ-007／008／014～017有限子场景 | `eval_20261028_01`：[事前约定](../evidence/course_ch03/eval_20261028_01/evaluation_agreement.md)、[文件清单](../evidence/course_ch03/eval_20261028_01/file_inventory.json)；客户端 `run_e2b938e432d044e69427e50f2b1a9aaf` 的[事件](../evidence/course_ch03/eval_20261028_01/artifacts/run_e2b938e432d044e69427e50f2b1a9aaf/events.jsonl)、[报告](../evidence/course_ch03/eval_20261028_01/artifacts/run_e2b938e432d044e69427e50f2b1a9aaf/report.json)、[Manifest](../evidence/course_ch03/eval_20261028_01/artifacts/run_e2b938e432d044e69427e50f2b1a9aaf/manifest.json) | 历史离线产品原件；仓库内可读 | [评价卡](P3_evaluation_observability_card.md)记录首次FAIL；缺report_sha256，后续DENY评价为证据不足。失败原件保留，不补写哈希制造通过 |
| 修复后R01授权拒绝；同一有限目标 | `eval_20261028_02`：[约定](../evidence/course_ch03/eval_20261028_02/evaluation_agreement.md)、[文件清单](../evidence/course_ch03/eval_20261028_02/file_inventory.json)；`run_ce4b0027ae024f05a72d81173c9f05e2` 的[事件](../evidence/course_ch03/eval_20261028_02/artifacts/run_ce4b0027ae024f05a72d81173c9f05e2/events.jsonl)、[报告](../evidence/course_ch03/eval_20261028_02/artifacts/run_ce4b0027ae024f05a72d81173c9f05e2/report.json)、[Manifest](../evidence/course_ch03/eval_20261028_02/artifacts/run_ce4b0027ae024f05a72d81173c9f05e2/manifest.json) | 历史离线产品原件；仓库内可读；是评价输入，不是评价器输出 | [评价卡第G节](P3_evaluation_observability_card.md)记录限定PASS；DENY／NOT_EXECUTED，无目标action；[当次验证JSON](../evidence/course_ch03/eval_20261028_02/verification.json)、[全量日志](../evidence/course_ch03/eval_20261028_02/full_suite_output.txt)。基线67242ba加[修复差异](../evidence/course_ch03/eval_20261028_02/execution_code_diff.patch)及[执行上下文](../evidence/course_ch03/eval_20261028_02/execution_context.json)，不能称原样HEAD；来源认证、OS停发证明及正式验收未建立 |
| Fixed／Dynamic对照；REQ-003／020／021 | 历史36次：[汇总](P3_offline_strategy_results.json)、[实验分析](P3_engineering_experiment.md)、[按Run定位原件](../evidence/course_ch04/strategy_history_36/README.md)、[108文件清单](../evidence/course_ch04/strategy_history_36/archive_manifest.json) | 合成夹具的历史离线运行及事后分析；仓库内可读 | 24次COMPLETED、12次异常STOPPED，不叫36次全通过；执行版本NOT_FULLY_BOUND，归档提交不是执行SHA；人工成本未测，不能证明普遍策略优劣或伙伴已复现 |
| Fixed个人取舍的来源核验 | 历史决定2026-11-09；2026-11-16[消息摘录](../review/P3_fixed_decision_source_excerpt_20261116.md)及[核验报告](../review/P3_fixed_decision_verification_20261116.md) | 历史用户消息的重新归档，不是实验输出；仓库内可读 | 暂时保留Fixed默认，Dynamic继续对照及重评；损坏外部原件未恢复，不作完整原文依据。2026-11-16负责人已接受归档及其限制，同日ADR-005有限范围Accepted（仅离线模拟基线，不代表C-02/REQ-021完成）；见[正式接受记录](../review/P3_adr005_acceptance_20261116.md) |

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

## 历史实验的 ADR 状态导航

[第四章历史实验报告](P3_engineering_experiment.md) §7 第 87 行的 Proposed 属于 2026-10-28 起的报告撰写时点。§9 第 97 行的未提交记述沿用第一轮候选语境，报告已入库（9754048、04214d3）。[现行 ADR-005](../design/ADR_005_deterministic_strategy_comparison.md)及[正式接受记录](../review/P3_adr005_acceptance_20261116.md)记载 2026-11-16 的有限内部离线接受。受保护报告原件逐字节保留，若要在原件加限定须单独授权。

36 次策略运行仍为 NOT_FULLY_BOUND，归档与执行身份分列；人工准备与复核成本未测，每格 3 次不支持统计显著性。Fixed 继续作为离线默认，Dynamic 作为对照及重评对象。C-02 完整比较及 REQ-021 正式验收仍待办。

## 历史测试数量及版本对账

各批次数量按对应日志或报告记录，执行身份与归档分别列出。全量、专项、重跑与静态引用不累加。当前 6B-2 只核对现存证据，产品测试、实验和模拟均为 NOT_REEXECUTED。私有原始日志按包内相对路径定位，公开索引不附私人原件。

| 阶段 | 执行日期 | 测试数量 | 测试范围 | 测试结果 | 执行版本 | 归档版本 | 原始依据 | 核验等级 | 限制 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 离线核心 | 2026-10-14 | 42 → 49 | 本地全量 | 均通过 | 离线核心初轮／审核修复，精确工作区未独立绑定 | `b3a0da7`（49 阶段节点） | [离线核心验证](P3_offline_core_validation.md) | 历史报告 | 不同子轮，不相加 |
| 无网络 HTTP 核心／C-1 | 2026-10-19 | 103／127 | 本地全量 | 均通过 | 对应两轮当时工作区，逐次执行 SHA 未独立绑定 | `bd888e2`／`e0e85d1`（阶段节点） | [核心报告](../review/P3_http_offline_core_review.md)、[夹具报告](../review/P3_mock_api_c1_review.md) | 历史报告 | 归档节点不代替执行 SHA |
| 后续接入准备 | 2026-10-19 | 148／154／157／158 | 本地全量，中间轮次及最终 | 均通过（报告） | `e0e85d1` 加当时工作区 | `30c98db`（交付与报告） | [开发审核报告](../review/P3_remaining_development_review.md) 第 65、72 行（原基线） | 历史报告 | 完整原始日志未取得 |
| C-3A/B 安全加固 | 2026-10-19 | 175 → 182 | 本地全量 | 均通过（报告） | `30c98db` 加当时工作区 | `3199b3f`（交付与报告） | [加固审核](../review/P3_c3_preflight_review.md) 第 47、57 行（原基线） | 历史报告 | 原始全量日志未取得 |
| C-3C 监督中间轮次 | 2026-10-21／22（分轮） | 213／217／227 | 本地全量 | 213 有 1 错误；217、227 通过 | `3199b3f` 加对应工作区快照 | `8019021`（日志）；`767b15e`／`8e56767`（交付） | [213 原日志](../evidence/course_ch03/c3c_supervisor_20261022/unittest-first.txt)、[217 原日志](../evidence/course_ch03/c3c_supervisor_20261022/unittest-second.txt)、[227 独立日志](../evidence/course_ch03/c3c_supervisor_20261022/independent-review-unittest.txt) | 原始日志 | 分别读取；对应中间工作区不推定为纯提交 |
| C-3C 后续修复 | 2026-10-21／22（分轮） | 237／257 | 本地全量 | 均通过（报告） | `3199b3f` 加对应工作区快照 | `8e56767`（审核） | [监督审核](../review/P3_c3_supervisor_review.md) 第 11、159 行（原基线） | 历史报告 | 未取得这两个数量的全量日志 |
| C-3C 最终交付 | 2026-10-22 | 258 | 本地全量 | 258 通过 | `3199b3f` 加当时工作区增量 | `8019021`（日志）；`767b15e`／`8e56767`（实现／审核） | [unittest-final.txt](../evidence/course_ch03/c3c_supervisor_20261022/unittest-final.txt)、[原差异与清单](../evidence/course_ch03/c3c_supervisor_20261022/INVENTORY_SHA256.json) | 原始日志 | 12 种重置竞争时序独立登记 |
| C-3D 本地与既有 CI | 2026-10-23；10-26 再出现于发布记录 | 278 | 本地全量／CI 历史运行 | 278 通过（报告） | 本地 `8e56767` 加 C-3D 候选；CI `c3ea320`（39925047670）、`cc7ab40`（40279651027）据历史报告 | `b79a4e3`（实现）、`c3ea320`（审核）、`cc7ab40`（阶段报告） | [实现审核](../review/P3_c3d_implementation_review.md)、[CI 旧查询与发布核验](../review/P3_offline_engineering_summary.md)；[Pack 原记录](../review/P3_spec_harness_pack_index.md)另记 40642916025 | 历史审核／CI 摘录 | 本轮未取得 CI 原日志或独立绑定 Pack 所引运行的 SHA；278 也是 Harness 原快照引用 |
| R01 修复与证据契约 | 2026-10-28 | 285 | 本地全量 | 285 通过 | `67242ba` 加当次代码差异 | `5c16b2b`（归档） | [全量原日志](../evidence/course_ch03/eval_20261028_02/full_suite_output.txt)、[执行上下文](../evidence/course_ch03/eval_20261028_02/execution_context.json) | 原始日志 | 与 36 次策略实验及其版本独立 |
| P1 冻结版回传 | 2026-11-25 | 562／153／71 | 全量／V2 专项／旧重点 | 三份日志均 OK | P1 记录的 `103a9ed` 冻结提交 | `cfbc89e`（去身份化验收记录）；日志在私有回传 ZIP | [回传验收](../review/P3_6b5a_peer_return_acceptance.md)，包内 `evidence/suite/full.log`、`v2.log`、`legacy_focus.log` | 原始日志 | 本轮按测试标识核实两个专项均为全量子集，交集 17；执行归属依 P1 回传记录 |
| 3B-2A 中间轮次 | 未取得精确执行日期 | 591／602 | 本机全量 | 591 通过；602 有 1 失败 | `103a9ed` 基线上的对应工作区快照 | 未入 Git 的本地日志；`711550a` 为后续正式交付 | 本机 3B-2A 工件 `baseline/full.log`、`integration/full.log`、`final/full.log` 及终端摘要；[范围设计](../review/P3_reviewed_scope_binding_design_review.md) | 原始日志 | 591 在两个中间日志分别出现；602 失败与 603 接受记录分开 |
| 3B-2A 接受轮次 | 未取得精确执行日期 | 603 | 本机全量 | 603 通过 | `103a9ed` 加接受轮工作区增量 | `711550a`（正式交付）；日志未入 Git | `accepted-terminal.txt`、`accepted/full.log`；[范围设计](../review/P3_reviewed_scope_binding_design_review.md) | 原始日志 | 源码归档提交与历史执行身份分列 |
| 3B-2B Windows 重做 | 未取得精确执行日期 | 617 | 实施与首次独立审核各一次全量 | 两份均 OK | `711550a` 加 Windows 重做工作区补丁 | Windows ZIP；最终工程提交 `7178dbb` 含后续 F1/F2 | [验收记录](../review/P3_reviewed_metrics_v1_acceptance.md)，Windows ZIP `test-results/full.log`；首次审核 `rerun/full.log` | 原始日志 | 首次审核准入仍 NEEDS_FIX |
| 3B-2B Windows F1 | 未取得精确执行日期 | 622 | F1 与第二轮独立审核各一次全量 | 两份均 OK | `711550a` 加 F1 工作区补丁 | F1 ZIP；最终工程提交 `7178dbb` 含 F2 | [验收历史](../review/P3_reviewed_metrics_v1_acceptance.md)，F1 ZIP `logs/full.log`；第二轮 `run/full.log` | 原始日志 | 第二轮审核准入仍 NEEDS_FIX |
| 3B-2B Windows F2 | 2026-11-25（既有核验记录） | 625 | F2 与第三轮独立审核各一次全量 | 两份均 OK | `711550a058d185ce81bef008f834afd846b76d1e` 加当时 F2 工作区补丁 | `7178dbbb5f3caedca6e7e53cf85a5785d70ecc82`（正式工程归档） | [矩阵 Evidence F](P3_acceptance_matrix_6b4.md#evidence-f)，F2 ZIP `logs/full.log`；第三轮 `run/full.log` | 原始日志 | 最近已核验产品技术基线；归档提交不是执行版本 |
| 3B-2B Linux 原报告 | 未取得 | 618 | 报告所述全量 | 报告称通过；未独立核验 | 未取得 | 未恢复 | [Windows 验收记录的历史说明](../review/P3_reviewed_metrics_v1_acceptance.md) | 历史报告／原件缺失 | Linux 实施成果、补丁及日志未恢复；单列，不并入 Windows |
| 6B-5B-2／F1 | 文档提交 2026-11-26 | 40 | 矩阵具名测试引用 | 静态核对数量 | NOT_REEXECUTED | `862a632`（文档提交） | [Acceptance Matrix](P3_acceptance_matrix_6b4.md) | 静态引用 | 原 36 加附录 4；不是全量或重新执行 |
