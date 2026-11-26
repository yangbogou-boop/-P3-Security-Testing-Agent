# 面向软件验收阶段的黑盒授权安全测试 Agent｜6B-5C-4 静态证据补充

正式文档基线 \`a5be2afb32ae8eeb9304c4714e4035d48d5a334b\`。本轮补充已存在的静态证据，产品、测试、模拟、实验及网络执行均为 \`NOT_REEXECUTED\`。

## 负责人关闭决定

负责人于 2026-11-26（Asia/Shanghai）在本轮任务中明确确认下列关闭决定。无另行签署凭据。P1 原意见位置见[回传验收](P3_6b5c_peer_incremental_review_acceptance.md)的 07 L15／L18，二者均为 ACCEPTED，独立审核建议由负责人确认收口。

| Finding | 状态 | 关闭范围 |
| --- | --- | --- |
| C-05 | CLOSED | 6B-5B-2／F1 已提交的 19 个 RC2 场景与 13 个额外细化场景的父子关系及显式导航。需求与场景验收沿用原记录。 |
| C-08 | CLOSED | 6B-2 已提交的 Harness 历史描述及根 AGENTS.md 权威入口。干净环境验证与 Stop／Rollback 仍是 GAP-003 待证事项。 |

原分级、原 Finding 登记及既有报告均按各自历史版本保留。

## 静态证据补充及状态承接

| Finding | 当前状态 | 本轮补充与建议 |
| --- | --- | --- |
| C-01 | STILL_OPEN | 保留正式场景缺口。 |
| C-02 | STILL_OPEN | 保留跨版本规范语义待确认。 |
| C-03 | ACCEPTED_WITH_LIMITATIONS | 保留正式计数措辞事项。 |
| C-04（低-中） | ACCEPTED_WITH_LIMITATIONS | 新增日志身份与访问范围，原人工意见继续有效。待 P1 复核增量。 |
| C-05（低） | CLOSED | 限场景导航。 |
| C-06 | ACCEPTED_WITH_LIMITATIONS | 保留不变量证据边界。 |
| C-07 | NEEDS_TEACHER_CONFIRMATION | 保留教师待办。 |
| C-08（低） | CLOSED | 限文档入口。 |
| C-09 | ACCEPTED_WITH_LIMITATIONS | 保留正式规范行与附录关系。 |
| P1-6B5C-N-01（中） | OPEN | 补五类版本固定摘录及访问矩阵，完整仓库和日志仍另取。建议 PARTIALLY_ADDRESSED。 |
| P1-6B5C-N-02（中） | OPEN | 补分轮日志字节、摘要、执行与归档身份。逐次工作区字节与缺件仍有限制。建议 PARTIALLY_ADDRESSED。 |
| P1-6B5C-N-03（低） | OPEN | 23 项 Git blob 复算一致，四处原始字节差异仅来自 CRLF／LF。新清单分列三种算法输入。建议 ADDRESSED_PENDING_PEER_REVIEW。 |
| P1-6B5C-N-04（低） | OPEN | 保留与 C-09 的关联。 |

## 版本、缺失证据与复核入口

[历史主台账](../eval/P3_experiment_evidence_index.md)仍作为集中对账入口。3B-2A 以 \`103a9ed36a696a9d686ed998a6fa9fd3472fea2c\` 及当时工作区增量为执行依据，两份 591 各自保留，602 有一次失败，603 为接受轮，正式归档为 \`711550a058d185ce81bef008f834afd846b76d1e\`。3B-2B 以 711550a 加各轮工作区增量为执行依据，Windows 实施与独审分别核到 617／622／625。首两轮独审为 NEEDS_FIX，第三轮为 PASS_WITH_NOTES，正式工程归档为 \`7178dbbb5f3caedca6e7e53cf85a5785d70ecc82\`。当前文档基线单列。原始日志确认数量与结果，完整执行字节仍按实际留存范围判断。

冻结版 562 为全量，153 与 71 均为子集且交集 17。40 项是[矩阵](../eval/P3_acceptance_matrix_6b4.md)静态具名引用。Linux 618 仅按历史报告保留，其实现、补丁、日志和执行身份未取得。部分完整独审正文、手册 [M]、P1 确认原消息及独立身份凭据仍缺失。原签署与身份边界沿用[回传验收](P3_6b5c_peer_incremental_review_acceptance.md)。

伙伴复核对象仅为 N-01～N-03 及 C-04，共四项，人工表留空。补充 ZIP \`P1_6B5C4_Static_Evidence_Supplement_a5be2af.zip\` 含 19 文件、23289 字节，SHA-256 \`d0a18b1122431d92c398758235bb8694aac7069addc9b1dbeea22db83243f483\`，包内清单 SHA-256 \`341a40bd7636615bf3485e190309731b8b4895b2f22bd0d27d5c41934bed0c5b\`。原分发、回传及 6B-5C-3 工件独立留存。

## 既有证据与课程边界

负责人内部接受仍为 ACCEPTED_WITH_LIMITATIONS，G02、G04、G06 为 PARTIALLY_SATISFIED。36 次历史对照 NOT_FULLY_BOUND，人工准备与复核成本未测，每格三次不能支持统计显著性。ADR-005 仅属有限内部接受，REQ-021 待正式验收，GAP-032 为 PARTIAL。

M7 NOT_CHECKABLE，M10 完整率 null，M12 NOT_MEASURED，M13 NOT_APPLICABLE。approval_verified=false、source_authenticated=false、runtime_authorisation_verified=false。文件完整性与外部来源及授权真实性分别核实。

GAP-001／002 仅有关闭建议。GAP-003 保持 PARTIAL，新三轮静态过程保留，干净环境与 Stop／Rollback 为 NOT_EXECUTED。GAP-004 D7 待负责人，GAP-005 待提交回执，GAP-010／024 为 PARTIAL，GAP-011 具备来源登记缺口关闭条件，GAP-017 待确认。E1～E3 和 T01～T05 待正式验收或教师确认。校准仍为三条规则各三次，共九次。

既有四处非阻断事项继续记录，分别为 6B-2 历史行号基线、6B-3 校准数量措辞、6B-5B-3「可先／必须先」、6B-5C-3 真实性字段及 GAP 导航。此处补记字段和状态，原 6B-5C-3 归档保留。指定稳定交付目录仍待落实，DELIVERY_PATH_PENDING。
