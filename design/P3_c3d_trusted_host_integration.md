# C-3D 可信宿主离线集成

状态：候选实现，待人工审核。仅 OFFLINE_SIMULATION，不是实际 HTTP 执行或许可。RC2、ADR、LocalRegistry、原 Controller、CI 和真实验收状态均不修改。

## 架构检查与复用

现有 SimulationRun 已包含独立候选匹配、三计数、终态、撤权 gate、单 I/O 所有者和响应判定。ServiceAdapter 是不监听的纯字节接口。AuthorizedService 则强制真实许可，不适合通过模拟许可调用；本轮不修改或调用其 start、serve_once、连接处理。EvidenceCoordinator 的 capture_controller 只接受精确 SimulationRun 类型，核对可信登记与落盘映射。Supervisor 已要求 sidecar VERIFIED 才能正式提交 Fixture。

新增 [trusted_host.py](../src/p3_core/trusted_host.py) 仅负责协调，使用现有固定六项配置、明确 synthetic 的离线 registry 和 FixtureManager。没有创建第二套 Controller、Supervisor 或许可系统。它不接受任意 URL、凭据、registry 或真实执行模式。

数据流：新 Fixture → SimulationRun.start → 固定 RunBinding → Supervisor 双端观察适配器 → Controller.step 准备批准动作 → capture_controller → Controller.step 推进 MemoryTransport 派发 → 完整内存请求交给 ServiceAdapter → 模拟服务端摘要交付协调器 → 原解析器及判定器 → 撤权和单所有者清理 → 客户端 finalize → sidecar finish／独立核验 → Supervisor.poll → 证据允许时 prepare_next → 有限离线报告。

内存传输仅收集 Controller 交付的字节，完整发送后才调用业务适配器。连接摘要的请求／响应大小来自本次内存交付；序号是模拟服务序号，不是 OS 发送证据。凭据字节只在内存中使用，读取或关闭后清空缓存。没有跨组件长锁；宿主入口锁仅声明一次性执行所有权。正式 Fixture 提交及失败通知继续使用原 Supervisor 短锁。

## 绑定与生命周期

run、fixture、scope、授权版本和起始 generation 被固定为 RunBinding；跨运行或字段不匹配被拒绝。Controller 撤权造成内部派发代次递增不改写该历史绑定。宿主不可重复执行；成功切换后旧适配器被失效，新 Fixture 使用新 ID 和新凭据，但不会自动启动下一运行。未绑定 sidecar 只允许观察清理，不允许提交。

真实 LifecyclePort 不支持 SimulationRun，因此新增最小离线端点适配器，只观察和撤权既有 Controller。内存服务端适配器仅包裹纯 ServiceAdapter，不伪装为 AuthorizedService，也不调用其许可接口。

## 未派发证明与状态映射

| 事实 | 输出与限制 |
| --- | --- |
| Controller DENY、没有 action | 原检查 NOT_EXECUTED、API INCONCLUSIVE；拒绝记录留在客户端，不伪造连接摘要 |
| 已 ALLOW，撤权发生在模拟发送前 | NO_MODEL_SEND_OBSERVED；只能观察本次内存模型，nondispatch_proof=UNAVAILABLE |
| 部分模拟发送后撤权 | MODEL_SEND_OBSERVED；无完整摘要时 EVIDENCE_INCOMPLETE，不变成 NOT_EXECUTED 证明 |
| 客户端审计失败 | send_observation=UNKNOWN；禁止通过缺失事件推断没有发送 |
| 完整模型响应及独立 sidecar 核验 | simulated_conclusion 可以 PASS/FAIL；实际 execution 仍 NOT_EXECUTED、API conclusion 仍 INCONCLUSIVE |

现有 Controller 未提供独立持久化的“不可再发送且从未发送”证明对象及协调器校验规则。不能只读 offset=0 或缺少服务端摘要就填补证据。因此本轮不增加 sidecar 豁免，登记动作缺摘要仍阻止切换。将来若需可恢复未派发证明，应设计不可重开终态、动作登记、发送序号、客户端审计完整性及来源绑定的共同契约，另行审核；本轮不改变 Controller。

## 审计与边界

客户端、sidecar、宿主生命周期分别使用独占 UUID 目录及 JSONL/Manifest/report。报告只存关联标识、固定原因、计数及原有脱敏检查结果，不存原始 Token、请求字节或异常正文。最后宿主报告写入失败会锁存 FAILED，清除新 Fixture 可用性，保留已经发生的提交事实，不声称回滚。

文件哈希不是来源真实性。可信根仍依赖可信 Python 宿主；不抵御同进程任意代码改写私有字段。全部模拟材料无权启动真实执行。现有 preflight 继续只诊断材料，不授予许可。14 项真实验收继续 PENDING_AUTHORIZATION；教师目录、目标所有者许可、可信人工核验来源、实际实例绑定和异常注入许可仍缺失。真实 OS 调度、双端来源认证、资源关闭和持久化故障恢复不在此次证明范围。
