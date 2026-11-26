# 6B-5B-3 负责人决策及版本化说明

**文档类型 `VERSIONED_NON_NORMATIVE_CLARIFICATION`。** RC2 仍是现行工程规范，原 GWT 仍是正式场景定义。本文解释已有条款和证据的适用范围，不改变规范要求、既有验收状态、执行授权或教师审批状态。

正式 Windows 基线为 `2a81c91a3cffff83afda3dbe3cb1dff2e6682ea2`。下文源码行号按该基线定位。P1 冻结版为 `103a9ed36a696a9d686ed998a6fa9fd3472fea2c`，其 T1～T4 结论限于冻结版。范围绑定归档为 `711550a`，带 F1/F2 修订的指标工程归档为 `7178dbb`。历史 625 项测试执行身份为 `711550a` 加当时 F2 工作区补丁。625 项两份全量日志为 F2 ZIP 的 `logs/full.log` 与第三轮独立审核 `run/full.log`；归档 SHA 不充当执行 SHA。[历史对账](../eval/P3_experiment_evidence_index.md#历史测试数量及版本对账) · [P1 验收及版本范围](P3_6b5a_peer_return_acceptance.md)

| 决策 | 负责人确认方向 | 本文落实 |
| --- | --- | --- |
| D01 | B，版本化验收范围说明 | 列已有证据和未覆盖的正式场景 |
| D02 | B，澄清版本及来源 | 核对冻结包、两版正文及工程适用范围 |
| D03 | C，分版本说明 | 按各自统计单位解释 V1／V2 |
| D04 | 规划开销内部单列，避免重复加总 | 限定历史计时关系及教师待确认项 |
| D05 | 同意七项候选条件，先核查已有证据 | 逐项记录证据和缺口，接受决定待负责人确认 |

批准依据为本轮负责人指令。D01～D05 为内部决策编号。无另行签名或签署时刻记录。

## D01｜授权失效及撤权验收范围

| 核查对象 | 规范及场景 | 已有证据与支持范围 | 未覆盖范围 | 适用版本 |
| --- | --- | --- | --- | --- |
| 启动输入缺失或矛盾 | RC2 REQ-001／012；GWT-N01 | N01 对应拒绝启动与无派发。合成校验已有输入缺失、矩阵冲突等局部断言 | 独立到期验收和真实行为 | RC2／V1；现行矩阵另列 V2 局部证据 |
| 启动时已到期 | RC2 §4 项7、§7、REQ-012；N01 为相邻输入边界 | V2 `test_expired_licence_blocks_start` 断言 STOPPED、AUTHORIZATION_INVALID、夹具启动为 0。F2 与第三轮日志各 L573 | GWT 未单列到期启动 | V2 冻结版日志 L515；当前工程历史 F2 有复核 |
| 运行中到期 | RC2 §4 项7、§7、REQ-012；无独立到期 GWT | V1 旧核心 `test_expiration_during_run` 记录 8 个计划、0 尝试、0 假派发及 AUTHORIZATION_INVALID，两份 F2 历史日志各 L155。HTTP 模型另有到期原因检查、回拨报错、撤权与预算耗尽并列记录，两份日志各 L305 | 真实在途 I/O、OS 隔离、单独正式原因码验收 | V1 旧核心及 HTTP 模型，按测试入口区分 |
| 到期时已接受、交付尚未消费 | RC2 §7；属于现有 V2 合成边界 | V2 `test_licence_expiry_between_accept_and_consume_aborts_ticket` 断言已有接受 1、消费 0、中止 1、夹具启动 0、AUTHORIZATION_INVALID。接受事实保留。两份 F2 历史日志各 L578 | 真实在途请求的撤回或取消效果 | V2 冻结版日志 L520；当前工程历史 F2 有复核 |
| 可信撤权及优先级 | RC2 §4 项7、§7、REQ-011；GWT-A03／A03-a | 规范规定同时触发时撤权优先。V2 准备后撤权断言不接受且取消 1；接受后撤权断言消费 0、中止 1、夹具启动 0。两份 F2 历史日志各 L583／584 | 无真实信号来源认证和真实在途控制证据。GWT-A03-a 的共同触发条件是撤权与时间耗尽 | RC2 规范；V2 合成；冻结回传日志 L524／525 |

P1-C-01 建议维持 `PARTIALLY_ADDRESSED`。是否新增独立到期正式场景由负责人另行决定，原 GWT 和正式授权保持现行状态。[RC2 §4、§6、§7](../brief/P3_specification_v1.0-rc2.md) · [GWT](../eval/P3_GWT_scenarios.md) · [原证据导航](../eval/P3_acceptance_matrix_6b4.md#c-01-已有授权证据导航) · [V2 断言](../tests/test_reviewed_runtime.py#L436)

## D02｜RC1 停止规则的历史来源

| 来源 | 原文位置及关系 | 当前解释范围 | 剩余限制 |
| --- | --- | --- | --- |
| P1 原观察 | 原表 01:18、05:18，记录 RC1 不在包内及停止规则不便判定 | 原记载及原分级保留。本轮查得原冻结分发 ZIP 含 RC1 原件 | 文件存在性更正与规则完备性是两个问题 |
| RC1 历史提议 | §7 L132。收到 5xx／无法解析预期 JSON，记录响应，无法可靠判定时 INCONCLUSIVE，证据足以确认违例时保留 FAIL；提出停止本轮并标记 RESPONSE_ERROR | RC1 历史快照 | 文中没有要累计连续 N 次的阈值 |
| RC2／GWT 现行口径 | RC2 §7 L134 引用 RC1 停止口径并记 RESPONSE_ERROR；GWT-N06 L32 将相关输入指向 §7 停止且不自动重试 | REQ-012／N06 的现有规范来源 | 正式证据仍需按场景核对；没有新增阈值 |
| 已有合成工程边界 | V1 HTTP 模型解析失败触发 RESPONSE_ERROR；协议中区分明确 FAIL 和 INCONCLUSIVE。V2 协议的 RESPONSE_ERROR 同样可标记候选判定 | 按各自实现、持久化语义及测试断言阅读 | V2 候选级 reason 无法单独证明 V1 整轮停止或真实 HTTP 验收。跨版本整轮停止契约未由本轮决定 |

冻结 ZIP SHA-256 为 `ffa669b4654232b025dfb3018e088241c0b787a7932024a579ac7899a6022f72`。成员 `P1_P3_Complete_Review/Frozen_Snapshot/brief/P3_specification_v1.0-rc1.md` 为 27,610 字节，SHA-256 为 `e3cec25af32ee5f8efc53d13833a354792137527e012511d3a4a572d1083e418`，与冻结 Git 对象及当前 RC1 比对一致。P1-C-02 建议 `PARTIALLY_ADDRESSED`。来源已定位，后续如需统一跨版本正式停止口径，由负责人显式决策。[P1 原登记](P3_6b5a_peer_finding_register.md) · [RC1 L132](../brief/P3_specification_v1.0-rc1.md) · [RC2 L134](../brief/P3_specification_v1.0-rc2.md) · [GWT L32](../eval/P3_GWT_scenarios.md) · [V1 模型](../src/p3_core/http/machine.py#L373) · [V2 协议](../src/p3_core/http/reviewed_protocol.py#L116)

## D03｜V1 与 V2 计数语义

| 术语或字段 | V1 HTTP 模型／RC2 的适用定义 | V2 审核合成运行的适用定义 | 可比性及证据限制 |
| --- | --- | --- | --- |
| 候选范围／计划 | 批准的候选供初始计划与追加使用，计划登记占名额而尚未开始尝试 | 审核候选全集 R 来自范围绑定的校验；登记槽位 S 是运行期间占用额度的对象 | 候选全集、运行计划和登记槽位分别统计。旧 V2 范围缺失时 R 和预算不可据当前配置倒填 |
| `plan_count`、提案、槽位 | 累计登记。初始与追加共享额度。新畸形提案可先建立 Controller 侧登记和关联标识，再拒绝。同 ID 已登记项不可替换、不可再占名额 | 累计已登记槽位。空值／非字符串不登记；未知非空候选 ID 可先占槽，随后 DENY；重复 ID 无额外槽位 | 两版同名字段都与槽位有关，入口定义不同。V2 合成占槽可计入 M9，未知 ID 无法进入 M2 有效审核候选 |
| `attempt_count` | Controller 对某槽位开始首次校验时加一，随后拒绝仍计一次；已登记未尝试不计。N04-d 细化新畸形提案“先登记、后尝试” | 授权决策数，`authorization_decisions = authorized + denied` | V1 的开始校验、V2 的已记录授权决策属于各自事件边界，直接汇总会混淆口径 |
| `request_count`／`model_request_count` | RC2 的 request_count 是事实上的 HTTP 派发。V1 合成模型记实际请求 0，模型请求按自身发送记账 | V2 实际请求计 0，模型请求等于接受数；接受、交付消费、夹具启动、夹具处理分别可计 | V2 可能已接受但中止且未消费，因此模型请求不可与 V1 模型发送或 V2 夹具执行等同 |
| 已处理／夹具处理 | 报告的 processed 属于槽位状态，拒绝亦可标记处理。课程历史覆盖只将明确模拟判定放入分子 | 运行器的 processed 可含拒绝。指标 P、H 根据关联证据以审核候选 ID 去重，H 需完整夹具处理证据 | 拒绝的槽位、已处理候选和已处理夹具是不同统计对象 |
| 明确判定 | 历史策略汇总按合成 PASS／FAIL 计覆盖，以当批批准候选为分母 | D 需有经同次证据校验支持的明确模拟 PASS／FAIL。M1=D/R，M4=D/P；冲突事实不提供有效数值，已核验分母保留 | 不以 V2 公式改写 V1 数值；INCONCLUSIVE 不属于 D；离线结果无真实系统外推 |
| 跨版本统一的“已处理数” | 无统一定义 | 无统一定义 | `DEFINITION_NOT_FULLY_ESTABLISHED`，继续分列 |

RC2 §4 项3／4与 GWT-N04-d 可按先登记再核验解读。分版本说明解决现有证据的阅读歧义，P1-C-03 建议 `ADDRESSED_PENDING_PEER_REVIEW`，请 P1 复核正式条款是否仍需措辞澄清。历史计数和运行边界维持原样。[RC2 §4](../brief/P3_specification_v1.0-rc2.md) · [N04-d](../eval/P3_GWT_scenarios.md) · [V1 登记与校验](../src/p3_core/http/machine.py#L246) · [V2 入口](../src/p3_core/http/reviewed_runtime.py#L368) · [V2 重放](../docs/P3_reviewed_evidence_v2.md) · [指标口径](../docs/P3_reviewed_metrics_v1.md)

## D04｜内部规划开销与课程七项指标

S3 物理第 42 张（稿036）列出覆盖、检出、误确认、未确定、工具故障、越界动作、成本。RC2 REQ-021 与 P05／P05-b 要求项目另报规划开销。治理登记-C-02 另报三种计数、规划与总时长、原始分子分母。治理登记-C-02 指策略取舍，P1-C-02 指历史停止来源，P1-C-07 指指标与基础闭环。

| 指标或字段 | 定义及单位 | 包含关系及适用范围 | 证据限制 |
| --- | --- | --- | --- |
| 覆盖 | 有足够判定证据的检查数／声明目标检查数；历史分子为明确模拟结果 | 历史 V1 合成。V2 M1 只在已验证审核范围内度量 | 跨版本候选分母和有效结论前提不同 |
| 检出 | 确认的已知缺陷数／夹具已知缺陷数 | 历史合成真值，分母 0 另记不适用 | V2 M13 缺独立真值，不能用模拟 FAIL 替代检出 |
| 误确认 | 与夹具真值不符的确认计数 | 历史夹具；按缺陷真值读 | V2 分布不证明误确认率 |
| 未确定 | INCONCLUSIVE 按历史记录定义计数 | V2 M6 按已核验的处理及结论事实统计，按其分母解释 | 不能将未处理项并入结论分布 |
| 工具故障 | 治理口径列检查级；历史汇总是按运行终止原因生成的 0／1 标志 | 历史 `tool_failures` 只能按其记录单位解释 | V2 M11 是可核验的原因分类，不能据此换算课程计数 |
| 越界动作 | 实际未授权派发数；另列被阻断意图 | 历史模型记录与实际网络分列；历史实际 0 处于无 socket 的合成约束中 | 不证明真实环境或独立 OS 层行为 |
| 成本 | 历史记录本地时长、规划、实际与模型请求、调用量等，各保留原单位 | 本地总耗时含内部规划；人工准备／复核字段为 null | 0 次实际请求或 LLM 调用是该模型记录；人工成本未知，不能填 0。V2 M12 未测 |
| `local_elapsed_seconds` | 秒，既有计时定义从 `run.start()` 前至 `run.finalize()` 后 | 包含此区间内的初始规划和动态选择 | 仅说明已归档 36 次的统计口径，逐次执行 SHA／环境仍 NOT_FULLY_BOUND |
| `planning_seconds` | 秒，累计运行模型中规划与动态选择的计时 | 内部单列，已含在此批总时长中，汇总时不再相加 | 其他版本按各自证据判断，正式课程归类 `COURSE_REQUIREMENT_NOT_SPECIFIED` |

36 次每格三次，24 次 COMPLETED、12 次异常 STOPPED，保留失败、未知与未覆盖，不能推导普遍优势或统计显著性。ADR-005 是负责人有限内部离线工程接受。S5 物理第 20、26 张支持按阶段和原单位分项、未知留缺；已核课件未指定规划开销应为成本拆项、独立评分字段或工程补充观察中的哪一种。P1-C-07 持续 `NEEDS_TEACHER_CONFIRMATION`。[来源登记](../brief/P3_decision_governance.md) · [RC2 REQ-021](../brief/P3_specification_v1.0-rc2.md) · [GWT](../eval/P3_GWT_scenarios.md) · [计时定义](../src/p3_core/experiments.py#L65) · [历史实验 §4、§6](../eval/P3_engineering_experiment.md) · [归档清单](../evidence/course_ch04/strategy_history_36/archive_manifest.json) · [ADR-005](../design/ADR_005_deterministic_strategy_comparison.md)

## D05｜内部基础闭环候选条件

| 条件 | 核查标准 | 已有证据 | 证据版本 | 支持范围 | 反向证据或缺口 | 建议状态 |
| --- | --- | --- | --- | --- | --- | --- |
| G01 需求与标准 | 需求与判定依据可定位 | [RC2](../brief/P3_specification_v1.0-rc2.md)、[GWT](../eval/P3_GWT_scenarios.md)、[Acceptance Matrix](../eval/P3_acceptance_matrix_6b4.md)；22 项及 32 个场景，含适用限制 | RC2／6B-4／6B-5B-2 F1（862a632） | 支持内部逐条读取和合成范围核查 | C-01 正式到期场景、C-02 跨版本适用性、C-07 课程门槛待确认。负责人确认所选内部判断范围 | SATISFIED_WITHIN_STATED_SCOPE |
| G02 输入与版本 | 输入、数据、执行身份和归档可分开追溯 | [R01 版本与证据](../eval/P3_evaluation_observability_card.md)、[V2 范围绑定](../docs/P3_reviewed_evidence_v2.md)、[历史对账](../eval/P3_experiment_evidence_index.md) | R01 67242ba（修复轮另有补丁）归档 5c16b2b；V2 冻结 103a9ed；F2 为 711550a＋补丁 | 已有明确绑定者可按所列版本复核 | 36 次逐次执行 NOT_FULLY_BOUND，事前实验卡未形成；Linux 618 只有历史报告。负责人选择可接受范围 | PARTIALLY_SATISFIED |
| G03 离线验证记录 | 可打开合成运行、输出和对应的历史记录 | [P1 T2～T4](P3_6b5a_peer_return_acceptance.md)、[R01 原件索引](../eval/P3_experiment_evidence_index.md)、[指标验收](P3_reviewed_metrics_v1_acceptance.md) | P1 冻结版；R01 两批；F2 执行身份见文首 | R01 保留首次失败及修复后结果；P1 Good 两组与冻结 V2 两组；两份 F2 全量日志均 625 OK | 属于各自历史样本。本轮 NOT_REEXECUTED，新版 V2 尚待 P1 增量复核 | SATISFIED_WITHIN_STATED_SCOPE |
| G04 证据完整性 | 可关联输出、日志、报告及清单，分开标识来源及签署边界 | [36 次 108 文件清单](../evidence/course_ch04/strategy_history_36/archive_manifest.json)、[P1 原件保全及关联复算](P3_6b5a_peer_return_acceptance.md)、[V2 证据协议](../docs/P3_reviewed_evidence_v2.md) | 历史策略归档；冻结 V2；范围及证据检查按 711550a／7178dbb | 静态对账可确认所读文件和同次内部记录关系 | R01 首次缺报告摘要；哈希不认证签署者、审核源或许可。负责人界定内部可接受范围，外部证明待补 | PARTIALLY_SATISFIED |
| G05 有限结论 | 区分合成结论、未覆盖及外部未确认 | [ADR-005](../design/ADR_005_deterministic_strategy_comparison.md)、[V2 缺值口径](../docs/P3_reviewed_metrics_v1.md)、[Evidence H](../eval/P3_acceptance_matrix_6b4.md#evidence-h) | 2026-11-16 离线接受；V2 7178dbb；6B-4／6B-5B-2 F1 | 保留无真值、未测成本、证据不足与作用范围 | 真实网络、课程验收及统计优势无证据，P1 后续复核范围仍有限 | SATISFIED_WITHIN_STATED_SCOPE |
| G06 可复核性 | 可依据版本、输入、原件、规程复查，并有实际独立记录 | [P1 T1～T4](P3_6b5a_peer_return_acceptance.md)、[Harness](../docs/P3_project_harness.md)、[伙伴指南](P3_peer_reproduction_guide.md)、[6B-2 历史对账](../eval/P3_experiment_evidence_index.md#历史测试数量及版本对账) | 103a9ed 实际回传；当前归档及现行导航 | 支持冻结版 R01 记录复核、Good 配对及 V2 记录复核 | P1 三轮审查过程尚缺，3B-2A／3B-2B 尚未由 P1 增量复核。需实际伙伴补证 | PARTIALLY_SATISFIED |
| G07 责任归属 | 自动化、负责人、伙伴、教师及其确认分别记录 | [AI 披露](P3_ai_usage_and_responsibility.md)、[签署核对](P3_6b5a_signature_reconciliation.md)、[D7 和人工工作表](P3_6b4_human_review_worksheet.md)、[治理登记](../brief/P3_decision_governance.md) | 6B-4 与 6B-5A；治理 2a81c91 | 明确责任归属，区分原签署记录、负责人转述和外部身份认证 | D7 本人签署、正式回执及 E1～E3 待取得；P1 确认原消息未复验。需本人和教师按职责处理 | SATISFIED_WITHIN_STATED_SCOPE |

建议负责人依据明确的版本及有限的合成范围审阅候选条件。现有材料支持局部内部工程判断，G02、G04、G06 仍部分满足。正式内部接受由负责人决定；本轮未作接受宣告。RC2 §2、§4 项3、REQ-021 与 P05 给出项目内先做基础闭环再比较的顺序。S3 物理 117 的开放、试跑清单与 S4、S5 的教学流程可供对照。P3 专用课程闭环门槛在已核课件范围内为 `COURSE_REQUIREMENT_NOT_SPECIFIED`，原手册 [M] 未取得。有限内部 ADR 接受、36 次历史比较及七项候选条件均不替代 REQ-021 正式验收。

## 九项 P1 Finding 回应

原编号、原分级与原始结论见[登记](P3_6b5a_peer_finding_register.md)。下列为 P3 建议状态，九项继续开放，均待 P1 后续复核。

| Finding | 原分级及问题 | 批次、证据和负责人决策 | 剩余问题 | 建议状态 | P1 复核 |
| --- | --- | --- | --- | --- | --- |
| C-01 | 中，授权失效场景缺口 | 6B-5B-2／D01；现有到期及撤权合成证据 | 是否增正式到期变体；核对接受与消费边界 | PARTIALLY_ADDRESSED | 待复核 |
| C-02 | 中，RC1 停止来源与可判定性 | 6B-5B-2／D02；冻结包原件、RC1 §7 与 RC2 §7 | 确认剩余跨版本适用性；正式场景证据仍有限 | PARTIALLY_ADDRESSED | 待复核 |
| C-03 | 中，登记和尝试定义冲突 | D03；RC2 §4 与 N04-d、两版计数事实 | 复核先登记后尝试及是否需要正式措辞澄清 | ADDRESSED_PENDING_PEER_REVIEW | 待复核 |
| C-04 | 低-中，历史测试数量缺对账 | 6B-2，集中证据索引；本轮继承 | 有些历史原始日志未取得，保留等级 | ADDRESSED_PENDING_PEER_REVIEW | 待复核 |
| C-05 | 低，19／32 场景关系 | 6B-5B-2 F1，附录场景导航；本轮继承 | 按原场景及局部证据复核 | ADDRESSED_PENDING_PEER_REVIEW | 待复核 |
| C-06 | 低，INV 验收缺反查 | 6B-5B-2 F1，附录五项映射；本轮继承 | 复核 INV-02 等证据范围 | ADDRESSED_PENDING_PEER_REVIEW | 待复核 |
| C-07 | 低，七项与规划开销、基础闭环 | 6B-3／D04、D05；计时口径及候选证据 | 正式课程归类、闭环门槛、REQ-021 验收 | NEEDS_TEACHER_CONFIRMATION | 待复核 |
| C-08 | 低，Harness 历史权威入口 | 6B-2，历史时点与根 AGENTS.md；本轮继承 | 入口整改范围内待复核；干净环境过程补证另计 | ADDRESSED_PENDING_PEER_REVIEW | 待复核 |
| C-09 | 低，REQ-001 缺正向追踪 | 6B-5B-2 F1，保留 N01 与部分 P01／P02；本轮继承 | 实际 HTTP 仍 PENDING_AUTHORIZATION | ADDRESSED_PENDING_PEER_REVIEW | 待复核 |

## 教师与负责人待确认

| 编号 | 问题及原始课程位置 | 当前内部处理 | 教师需确认及未确认影响 |
| --- | --- | --- | --- |
| T01 | 规划开销课程归类，S3 物理 42／73、S5 20／26 | D04 单列且避免重复加总 | 成本拆项、独立评分或工程观察；目前保留课程七项 |
| T02 | P3 专用基础闭环门槛，S3 117、S4 32／37、S5 36／37 | D05 只核查内部证据 | 是否另有统一可判定门槛、可模拟证据适用范围；课程闭环未验收 |
| T03 | REQ-021 正式策略对照验收，S3 42／73／115、S5 6～12／37～38 | ADR-005 有限内部接受，按历史口径保存结果 | 正式可比条件、样本、人工成本及复核凭据；正式验收仍待办 |
| T04 | D6 六类校准的跨规则范围，S3 90／91、94、114（页脚 116）、117 | 三条规则各三次，共九次历史校准记录。K1／K2 部分语义对应，K3 仅预期状态相似 | 确认跨规则适用及缺项；GAP-017 待确认，现有九次未覆盖完整六类 |
| T05 | 原审批、预算冻结、契约、Rubric 与 E1～E3 凭据，S3 37～40、74、81、85、115～117 | 治理 A-01～A-06 保留原状态 | 核对已有正式凭据及适用范围；原审批和提交状态不提升 |

负责人仍需决定是否接受上述内部范围、D01 是否另立正式场景、D02 是否另立版本统一停止规则、D03 是否需要正式术语修订，以及后续记录的版本计时边界。D7 由负责人本人核查签署，GAP-005 需实际课程提交及回执。GAP-003 仍需 P1 本人提交边界质询、三条实际 MUST 反追踪、干净环境 Harness 走查及实际命令、停止与回滚记录，并记录版本、日期与未查范围。[课程治理](../brief/P3_decision_governance.md) · [校准对照](P3_6b4_calibration_alignment.md) · [原 GAP](P3_course_gap_register_20261118.md)

## RC3 必要性评估

| 决策 | 说明足以落实本轮 | 当前所需规范修改 | 后续批准条件 |
| --- | --- | --- | --- |
| D01 | 是，定位现有证据与到期空缺 | 无 | 独立正式场景如需新增须单独批准 |
| D02 | 是，纠正来源事实并保留语义边界 | 无 | 新规则、阈值、跨版本执行要求须独立决定 |
| D03 | 是，分开解释同名字段与版本 | 无 | 若将来改写正式计数契约须版本管理及负责人批准 |
| D04 | 是，历史计时范围下单列规划 | 无 | 正式课程归类由教师确认；其他版本计时需自身证据 |
| D05 | 是，按七项核查历史证据 | 无 | 内部接受由负责人决定，写入正式规范或课程门槛须另行批准 |

本轮维持 RC2，无需发布 RC3；当前结论只涵盖说明、来源和证据。在仓库外继续保留 6B-2 行号基线表述的既有 MINOR 与 6B-3 校准数量措辞的既有 MINOR，两份旧工件不重制。

## 既有成果与证据边界

Acceptance Matrix 的 22 项唯一需求、每项 16 字段、20 MUST／1 SHOULD／1 MAY、32 条 GWT 场景（13 条额外细化）、五项 INV、40 项具名测试引用全部沿用。REQ-013／020／021 部分完成，REQ-021 正式验收待办，REQ-022 为 MAY 且未接入。V2 M7 NOT_CHECKABLE，M10 完整率为 null，M12 NOT_MEASURED，M13 NOT_APPLICABLE。具体对照候选身份尚不可独立证明，三个真实性字段 `approval_verified`、`source_authenticated`、`runtime_authorisation_verified` 均为 false。

GAP-001／002 仅具备关闭建议，GAP-003 待 P1 本人补证，GAP-010／024 部分完成，受保护实验文件待另行授权，GAP-032 工程评估 PARTIAL。原手册 [M] 缺失，课程课件核查基于可读原生正文及既有备注提取，未完成逐像素渲染验证。625 项为历史技术审核。本轮产品代码、单元测试、模拟及实验均为 `NOT_REEXECUTED`。
