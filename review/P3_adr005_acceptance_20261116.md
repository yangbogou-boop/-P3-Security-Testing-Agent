# P3 ADR-005 有限范围内部工程接受记录

## 1. 文件身份

- 标题：P3 ADR-005 有限范围内部工程接受记录
- 记录日期：2026-11-16（Asia/Shanghai）
- 决策主体：P3 项目负责人
- 决策类型：内部工程技术选择
- 适用范围：当前离线模拟工程基线
- 决策对象：[ADR-005](../design/ADR_005_deterministic_strategy_comparison.md)
- 状态：`OWNER_CONFIRMED_LIMITED_ACCEPTANCE`
- 状态说明：该值是本记录的语义表达，不是软件已定义的正式状态枚举，也不是教师批准状态或课程验收结论。

## 2. 4A 归档复核结果

项目负责人于 2026-11-16 确认采用结论 A：接受当前 Fixed 历史决策归档及其明确限制。接受范围包括：

- [历史用户消息摘录](P3_fixed_decision_source_excerpt_20261116.md)：2026-11-09 的决定、理由、适用范围、重评条件与责任分工；
- 可追溯来源与当前文本完整性（围栏段落 1,600 字节，SHA-256 `152364b535b80696a90ef9d533c9d97cc67d381a37d13618619c8f0a5593ad52`）；
- 损坏原件未恢复的事实（外部原件 1,610 字节，SHA-256 `1c7372d6e7657a7d0d8ea8636a4a93b5ba6f52d41d0e81f36028988132dbf65b`，664 个 `0x3F` 问号）；
- 无独立数字签名的限制；
- 历史执行版本绑定不完整的限制（`NOT_FULLY_BOUND`）。

边界：该确认只针对归档的可信性、内容与限制，**本身不构成对 ADR-005 的接受**。不得据此声称损坏原件已恢复，也不得声称负责人亲自执行了全部历史实验。

## 3. ADR-005 正式决策

项目负责人于 2026-11-16 正式确认：接受 ADR-005 为仅限当前离线模拟工程基线的内部技术决策；Fixed（`fixed-v1`）继续作为默认策略，Dynamic（`evidence-priority-v1`）继续作为对照。

限定范围：

- 仅限已有合成夹具、已登记候选与当前工程约束下的离线模拟基线；
- 不代表 C-02 完整完成；
- 不代表 REQ-021 正式课程验收；
- 不代表教师批准、预算冻结或正式评分契约；
- 不代表真实 HTTP 执行授权；
- 不表示 Fixed 在所有环境下最佳，也不表示 Dynamic 被永久放弃。

重新评估条件保持：[ADR-005 Reconsideration](../design/ADR_005_deterministic_strategy_comparison.md#reconsideration) 与历史原话所述条件不变。

## 4. 工程审核依据

2026-11-16 只读审核（4B）覆盖以下材料：

- [ADR-005](../design/ADR_005_deterministic_strategy_comparison.md)
- [strategies.py](../src/p3_core/http/strategies.py)
- [machine.py](../src/p3_core/http/machine.py)
- [test_remaining.py](../tests/test_remaining.py)
- [P3_offline_strategy_results.json](../eval/P3_offline_strategy_results.json)
- [P3_engineering_experiment.md](../eval/P3_engineering_experiment.md)
- [36 次归档说明](../evidence/course_ch04/strategy_history_36/README.md)
- [P3_decision_governance.md](../brief/P3_decision_governance.md)

审核结论：

- `FixedSelection` 按固定候选登记顺序选择未完成项；
- `EvidenceSelection` 依据 Controller 提供的已完成断言与必要对照关系确定顺序，不读取原始响应；
- 两种策略只负责候选选择，不授予执行权；授权、预算、停止与证据边界由模型独立执行；
- 未发现阻断有限内部工程接受的代码问题；
- 36 次历史离线实验支持“暂时保留 Fixed”的保守选择；
- 现有证据不足以证明 Fixed 普遍优于 Dynamic，也不支持统计显著性声明。

**该审核为静态代码与历史证据分析：未执行新的产品测试、未重跑 36 次实验、未运行真实 HTTP。** 测试定义的存在不等于测试通过；本轮没有新增测试结果。

## 5. 未完成事项及接受边界

| 事项 | 状态 |
|---|---|
| 内部工程决定（本记录） | 已接受（2026-11-16） |
| C-02 完整实验条件 | 未完成（实验卡预注册、正式样本量、人工成本） |
| REQ-021 正式课程验收 | 未完成 |
| 教师审批与班级预算冻结 | 未完成 |
| 真实 HTTP 授权（14 项） | `PENDING_AUTHORIZATION` |
| 独立 OS 未派发证明 | `UNAVAILABLE` |
| 36 次历史执行版本绑定 | `NOT_FULLY_BOUND` |
| 人工准备与复核成本 | `NOT_MEASURED` |

## 6. 确认来源与责任

- 本记录的负责人决定依据为本轮对话中项目负责人的明确确认。
- 未附独立数字签名，也未提供平台原始消息导出；不伪造人工手写签署。
- 不自动认证消息发送者的外部身份；本记录只表明“项目负责人已明确确认，由分析代理整理成文”。
- 未增加虚构的审核人、已完成的签名栏或教师审批编号。
- 本记录不替代课程验收、教师审批、目标执行授权或正式评分契约。
