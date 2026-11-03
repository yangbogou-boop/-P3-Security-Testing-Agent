# 第一章任务B：Controller拒绝未登记端点

制作日期：2026-11-02；代码核对基线 `f5d26f41f403e9c22f97be30fe9fb44a73294c44`。本作业关联 [GWT-N03](../eval/P3_GWT_scenarios.md) 与 [RC2](../brief/P3_specification_v1.0-rc2.md) P3-REQ-008／015，不新增正式需求ID，不替代完整HTTP验收。

课程依据：《AI原生工程实践课程》第一章第61张任务B、第38张四问。本文为实际作业文件；课程提交与人工签署尚未完成。

## Given–When–Then

**Given**：离线 Controller 具有有效合成配置、一个已批准候选、充足检查／时间预算和可控假派发器。用测试时钟固定逻辑时间及有效授权时间。复制唯一候选，仅将 `endpoint_id` 从已登记的 `object` 改为未登记的 `unknown`；其余字段保持原值。测试替身 Planner 只返回这一提案，不授予权限。

**When**：调用一次 `Controller.run()`，传入返回上述单提案的规划输入。

**Then**：

| 可观察结果 | 精确断言 |
|---|---|
| 授权 | DENY |
| 执行 | NOT_EXECUTED |
| API结论 | INCONCLUSIVE，不能称API安全PASS |
| 累计计数 | plan_count=1、attempt_count=1、request_count=0；该离线核心的offline_dispatch_count=0 |
| 假派发器 | calls为空，没有调用record |
| 拒绝依据 | result.reason及关联authorization_decision事件reason均为UNREGISTERED_ENDPOINT；事件decision=DENY，slot_id和attempt_id与结果匹配 |

拒绝消耗登记及首次尝试名额；不是“拒绝即预算归零”。所有已登记项处理完时本例可COMPLETED，不强行要求STOPPED。这里是原离线Controller，不能混用HTTP模型的model_request_count或第三章另一运行的7/7/0/6计数。

## 当前实现与测试对照

- [controller.py](../src/p3_core/controller.py)：`run()`启动并处理计划；`_authorize()`首先查找endpoint，未找到返回UNREGISTERED_ENDPOINT；`_attempt()`记录拒绝，只在没有拒绝原因时调用派发器。
- [models.py](../src/p3_core/models.py)：CheckResult初始执行／结论为NOT_EXECUTED／INCONCLUSIVE；该拒绝路径保留这两个值。
- [test_core.py](../tests/test_core.py)：主要核对 `CoreTests.test_structured_unauthorized_plan_items_are_denied_and_counted`。其第一个子情境仅改变endpoint_id；原测试断言计数（含offline_dispatch_count=0）、DENY、INCONCLUSIVE及COMPLETED。
- 原测试没有单独断言本例的execution、dispatcher.calls和具体拒绝原因。本作业不声称它覆盖所有Then；本轮用独立内存核验补查上述输出，不修改产品或原测试。实际验证结果见下方记录。

## 四个自检问题

| 问题 | 结合P3的回答 |
|---|---|
| Q1 Given状态是否可构造？ | 复用test_core.config(1)，复制候选只修改endpoint_id，使用Clock、OfflineDispatcher及MemoryEvidence。固定时钟使授权有效、预算充足；不需服务器、真实账号或网络。 |
| Q2 When动作是否可触发？ | 一次调用公开run入口并传入只返回该提案的Planner替身即可。登记、首次尝试和拒绝审计属于此单一动作内部，不再拆成多个When。 |
| Q3 Then结果是否可断言？ | 读取结果枚举、计数字典、假派发器calls与内存事件；逐项比较明确值，并通过slot/attempt关联原因，而不是判断自然语言“安全”。 |
| Q4 规格是否与具体实现解耦？ | 规格限定输入、公开触发动作及可观察输出，不规定私有函数、锁、循环顺序或随机ID值。当前用run作为实际入口；将来等价实现仍应满足相同拒绝、计数、无派发和审计约束。函数名仅用于现版本定位。 |

## 验证记录

2026-11-02实际执行：在测试模块导入、加载之前安装socket审计阻断及socket/DNS入口替身，使用Python隔离模式和禁止字节码写入。运行原有指定测试 **1项，OK，0.009s**（内含原有7个参数变体，不能算7项独立unittest）；另做 **1次仅修改endpoint_id的内存核验**，逐项断言本作业Then，全部通过，进程退出码0。未执行全量套件，未新增仓库测试文件。

实际观测：DENY／NOT_EXECUTED／INCONCLUSIVE；reason=UNREGISTERED_ENDPOINT；plan_count=1、attempt_count=1、request_count=0、offline_dispatch_count=0；dispatcher.calls长度0；匹配的authorization_decision事件1条；运行COMPLETED。使用MemoryEvidence，未写入产品Evidence。

本次外部验证命令：`python -B -I -S D:\codex\P3_ch01_validation_20261102\validate.py`；本机辅助脚本及日志位于 `D:\codex\P3_ch01_validation_20261102\`，不在仓库，不当作跨机器已发布附件。日志中的PowerShell NativeCommandError包装来自unittest写stderr；测试汇总为OK、Python实际退出码为0，不应把包装误当作测试失败。本段保存实际摘要；如需独立重跑，由负责人提供脚本原件并核对保护范围。

上述是受控离线验证，不是陌生AI阅读测试，也不是历史390项CI的新执行。

本例只证明受控离线场景的拒绝语义，不认证真实许可、OS行为或14项HTTP验收。第一章任务A的陌生AI阅读测试另见 [阅读测试准备](P3_course_ch01_AI_reading_test.md)。
