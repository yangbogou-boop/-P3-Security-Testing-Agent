# P3 6B-4 需求证据追踪与课程材料对齐

实施日期 2026-11-25（Asia/Shanghai）。技术证据基线为 `7178dbbb5f3caedca6e7e53cf85a5785d70ecc82`，标题 `feat(metrics): 新增V2审核证据离线评价指标`。本轮使用原 Windows 正式工作区，开始时 main 与本地 origin/main 指向该提交，领先／落后 0／0，工作区及暂存区无待处理内容。origin/main 是本地远端跟踪引用，本轮未刷新远端引用。

## 实施结果及 GAP-013～018 追踪

| GAP | 本轮已补齐 | 继续缺少的依据 | 状态建议，待负责人审批 |
| --- | --- | --- | --- |
| GAP-013 | [Acceptance Matrix](../eval/P3_acceptance_matrix_6b4.md)覆盖 P3-REQ-001～022，保留 16 个字段。原[追踪历史](../eval/P3_requirement_traceability.md)可继续使用 | 每条正式验收记录和 36 次逐次历史执行身份仍缺；R01 整改后有当次补丁和上下文，执行版本保留工作区差异 | 文档字段与路径索引可验收。负责人核查后可关闭文档子项，保留历史版本及课程缺口 |
| GAP-014 | [AI 披露](P3_ai_usage_and_responsibility.md)逐项给出活动依据，分开记载 AI 协助、责任和签署 | 完整调用记录和人工确认，D7、P1 复现与教师审批尚无新增结果 | 披露文档可验收，待负责人确认；其余人工活动保留 |
| GAP-015 | [AS-01～05 工作表](P3_6b4_human_review_worksheet.md#assumption-责任确认)保留原文，提供建议角色、证据及事件门槛 | 实际责任人、验证门槛和状态由负责人确认 | 保持待确认，PENDING_OWNER_CONFIRMATION |
| GAP-016 | [CH03 评价工作表](../eval/P3_evaluation_observability_card.md)按课件页脚 38 六项补齐，分别给出 R01 首次和整改后记录 | 独立人工复核、版本限制及课程验收状态未变 | 六字段补齐的文档子项可验收，保留人审和正式验收待办 |
| GAP-017 | [K1–K6 校准对照](P3_6b4_calibration_alignment.md)区分课程口径、历史产品证据和合成输入 | K1–K3 正式对应口径与 K4～K6 的证据形态，等待教师确认 | 保持部分完成 |
| GAP-018 | [Harness 可用性证据表](../docs/P3_project_harness.md)列出文档、相对命令、当前入口、历史环境及边界 | 独立伙伴复现、统一可复用的隔离启动方式与独立 OS 级证明尚无本轮证据 | 保持部分完成，以已有文档核对为限 |

本轮保持[原 GAP 登记](P3_course_gap_register_20261118.md)及其状态。独立 Global、Plan、Tasks 原件沿用未定位结论，任务背景依据[课程索引](P3_course_delivery_index.md)、既有任务卡和原项目治理记录。

## 22 项追踪如何核对

- [RC2](../brief/P3_specification_v1.0-rc2.md)原文与优先级逐条对照。20 项 MUST、1 项 SHOULD、1 项 MAY。逐条列出 [GWT](../eval/P3_GWT_scenarios.md)、设计、实现和验证依据，并将执行版本、归档版本与范围分别记录。
- REQ-001～012、014～019 有对应离线实现和自动证据。REQ-013 的真实 HTTP 组件证据停留在替身和边界验证。REQ-020 有离线元数据验证，真实 HTTP 集成验收不足。REQ-021 有 36 次历史模拟策略对照，正式课程验收仍待完成。REQ-022 是 MAY，当前未接入真实 LLM。
- 逐条矩阵中引用的具名测试对照当前测试定义及历史详细日志中的单项结果。F2 Windows 实施日志与第三轮独立提交前审核日志的相关记录一致，工件见矩阵 Evidence F。全量 625 项与 22／194／40／13／71 各分组为以前的审核记录，分组有交集，不作为本轮执行记录或任一条需求的替代证据。
- 五个 V2 切片 9c59064、3af990d、103a9ed、711550a、7178dbb 分别对应契约、运行、校验、范围、指标。矩阵保留其归属和监管边界，V2 业务样例、证据轴及 M 指标不会单独成为课程新要求。

## 历史与指标边界

[R01 索引](../eval/P3_experiment_evidence_index.md)保留首次 FAIL 与整改后有限 PASS 的原件和各自版本。整改后执行的 Git 基线、当时脏工作区摘要和归档提交分别登记。V2 的独立校验与评价没有重新认证历史执行过程。

[36 次归档](../evidence/course_ch04/strategy_history_36/README.md)保留 `NOT_FULLY_BOUND`、归档身份和每格三次重复。历史事前卡未形成、人工准备与复核耗时未测量，样本不能支撑统计显著性。[ADR-005](../design/ADR_005_deterministic_strategy_comparison.md)仍是有限范围内部工程接受，C-02 与 REQ-021 正式验收仍未完成。

[V2 指标](../docs/P3_reviewed_metrics_v1.md)保留 M7 `NOT_CHECKABLE`、M10 完整率 `null`、M12 `NOT_MEASURED`、M13 `NOT_APPLICABLE`。具体对照候选身份及外部审核来源仍无独立认证，`approval_verified`、`source_authenticated`、`runtime_authorisation_verified` 均为 `false`。GAP-032 的工程评估保持 `PARTIAL`。原登记仍保留初始状态及教师原话、正式通用性要求尚无书面记录的限制。是否需补更多证据，由正式课程契约、项目范围和教师书面确认决定。

## 人工复核及版本冻结

[人工工作表](P3_6b4_human_review_worksheet.md)包含 22 项核查、AS-01～05、AI 责任确认、D7 空白签署、P1 待办和教师题单。P1 冻结包保留在 103a9ed，3B-2A/3B-2B 增量只列待核查索引。本轮无 P1 人工结果、D7 签署、课程回执或教师批准。

## 变更与交付核查

| 文档 | 变更 |
| --- | --- |
| [历史需求追踪](../eval/P3_requirement_traceability.md) | 追加矩阵入口 |
| [评价观察卡](../eval/P3_evaluation_observability_card.md) | 追加 CH03 六字段 R01 对照 |
| [AI 使用披露](P3_ai_usage_and_responsibility.md) | 追加活动依据及责任边界 |
| [项目 Harness](../docs/P3_project_harness.md) | 追加可用性证据表 |
| [22 项 Acceptance Matrix](../eval/P3_acceptance_matrix_6b4.md) | 新增 |
| [课程校准对照](P3_6b4_calibration_alignment.md) | 新增 |
| [人工工作表](P3_6b4_human_review_worksheet.md) | 新增 |
| 本报告 | 新增 |

本轮没有复跑产品测试或模拟运行，所列运行命令均为 `NOT_REEXECUTED`；文档本地链接、结构及补丁检查以交付包内 `validation.txt` 的真实输出为准。产品源码、测试、RC2、历史 Evidence、ADR、GAP 状态及原课程输入不在改动范围。无暂存、提交或推送。

指定 Windows 稳定目录状态为 `DELIVERY_PATH_PENDING`，交付采用可访问的持久化位置。交付包包含本报告、全部八份当前文档、对应完整补丁、SHA-256 清单与核验输出。复核通过后可安排 6B-4 独立提交前审核，由负责人决定后续 6B-5 人工活动。

## 6B-4-F1 证据引用整改

首次 6B-4 实施与第一次独立提交前审核均核查 34 个具名测试。第一次独立审核结论为 NEEDS_FIX，登记 6B4-01、6B4-02（MAJOR）及 6B4-03（MINOR）。本轮仅修正矩阵的三行及对应证据说明，并追加本节。实施自检完成，第二轮独立审核待办。

### 三项发现整改对照

| 发现 | 整改前 | 整改后与实际断言 | 历史执行与归档 | 剩余限制／实施自检 |
| --- | --- | --- | --- | --- |
| 6B4-01／REQ-003 | 仅引 test_strategy_repeatable，范围写为固定及动态选择 | 保留动态测试，新增 test_fixed_plan_is_deterministic_and_does_not_mutate_config。两次 FixedPlanner 规划使用同一解析候选集，结果相同；另断言修改原配置后派发仍使用已解析参数。动态测试比较两次默认合成运行的顺序 | F2 实施及第三轮独立技术审核的 full.log 第 158、412 行；版本说明见下表 | 单元规划及一个动态场景，历史 36 次执行仍 NOT_FULLY_BOUND。引用与范围自检通过 |
| 6B4-02／REQ-019 | 仅引 validate 权限测试和历史只读评价，范围写为现有离线入口 | validate 对测试配置返回 0 且仍标 PENDING_AUTHORIZATION；新增 test_cli_and_read_only，核对 offline --output 的合成生成分支与 offline --run 的既有报告读取均返回 0，且既有证据目录文件字节一致。静态核对 delivery.py，前者经 run_scenario 写入新运行再读取摘要，后者直接读取既有运行 | 上述两份 full.log 第 397、373 行。Evidence E 属 5a6e81a 加当时工作区状态的历史评价器调用，输出移交 8019021 | 测试未逐字段核对新报告，伙伴环境可移植性未核验。引用与范围自检通过 |
| 6B4-03／REQ-022 | 归档版本带 HTTP 待授权清单 | 以 RC2 和 GWT-A04 为可选范围依据，改为无实际 LLM 执行及不适用、无运行原件 | 无适用执行或归档版本 | MAY、未接入状态保持，引用自检通过 |

### F1 新增测试引用核验

| 方法及归属 | F2 实施 ZIP 内 logs/full.log | 第三轮独立技术审核 run/full.log |
| --- | --- | --- |
| test_core.CoreTests.test_fixed_plan_is_deterministic_and_does_not_mutate_config | 第 158 行，ok，一次 | 第 158 行，ok，一次 |
| test_offline_summary.OfflineSummaryTests.test_cli_and_read_only | 第 373 行，ok，一次 | 第 373 行，ok，一次 |

两次历史执行均以 711550a 加 F2 工作区补丁为版本依据；本轮对正式工作区只读反向校验该补丁，并与 7178dbb 的上述测试源码逐一比对。可交付的实施日志归档于矩阵 Evidence F 所链接的 F2 ZIP，第三轮独立日志为当时本机归档。修订后矩阵按模块、类及方法去重为 36 项，两个新增引用均为独立方法，两份历史日志均可定位。625 项是既有技术审核结果。本轮产品测试及模拟运行仍为 NOT_REEXECUTED。

本轮有限同类核对保留每项验证的实际边界。REQ-010 的具名断言用于预算计数和范围绑定，逻辑时钟、串行及无新增证据停止的子项不由这些断言一并判定。REQ-013、020、021 仍为部分完成。原 GAP 登记、GAP-032 工程 PARTIAL 评估、D7 签署、Assumption 责任及 E1～E3 课程验收边界沿用既有记录。

据负责人转述，已收到 P1 针对原冻结版本的回传材料，P1 本人确认审查表已全部签署。材料及签署的专项验收待后续 6B-5A，本轮未复核原件或 P1 Finding，GAP-001～003 未关闭。原 P1 冻结包及回传件均保持原样。

F1 独立交付包 P3_6B4_F1_7178dbb.zip 单独保存，原 6B-4 实施 ZIP 与首次独立审核结论保留。指定 Windows 稳定目录仍为 DELIVERY_PATH_PENDING。
