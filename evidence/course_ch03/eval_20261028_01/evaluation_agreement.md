# 执行前评价约定

2026-10-28，先于本目录定点测试和演示执行写入。基线及实际文件哈希见 execution_context.json。此文件是评价约定，不是原始运行结果。

对象：已有 OfflineHost 使用的 SimulationRun._authorize；拒绝未批准候选后不得生成该动作的派发，并留下可关联拒绝记录。关联 P3-REQ-007、008、014、015、016；覆盖 GWT-N03／A02 的未批准候选子场景及 N07 的模拟／有限结论子场景，不宣称全部场景完成。

输入：mode=good、fault=deny。复用 host.execute 的现有输入构造：复制当前六项候选中的第一项，只将 check_id 改为 unapproved。身份、端点、只读方法及批准参数组合继承原候选；精确非敏感输入在 host 初始化后、execute 前保存为 input.json。批准集合为 six-v1，夹具 synthetic-v1，契约 p3-http-v1，模拟许可不产生真实执行权。

预期：恰好一个 DENY，原因 NOT_APPROVED_CANDIDATE，execution=NOT_EXECUTED，conclusion=INCONCLUSIVE，action_id=null；拒绝行可按 slot_id／proposal_id／attempt_id 关联 authorization 事件，不能存在该 slot 的 prepared 或 model_io。六项合法候选可以模拟派发，最终 plan_count=7、attempt_count=7、request_count=0、model_request_count=6。JSONL 与 Manifest 哈希一致，报告无 audit_gap。原始模拟凭据不得出现在持久化文件或返回结果。

执行方式：CPython 3.9.12，python -I -S -B - 读取本次归档的内联命令；不新增产品或测试入口。sys.addaudithook 在项目导入和 unittest discovery 前拒绝 socket.*、子进程及外部执行事件，禁止动态库加载旁路。仅执行原 HostTests.test_controller_denies_unapproved_candidate 一项，再通过原 OfflineHost API 运行一次同输入持久化演示。测试临时输出由原测试自行管理，独立演示输出保存于 artifacts。未运行另一套 core 测试、全量套件或第四章比较。

安全静态检查：OfflineHost 使用 _Wire(MemoryTransport) 与 _ServicePort／ServiceAdapter，未调用真实 AuthorizedService.start 或 AuthorizedHttpRun 派发；Supervisor 的依赖会导入 live/service 类定义，但没有模块顶层创建 socket 的调用。隔离启动不加载 site 和用户启动定制；审计钩子不等于 OS 防火墙，不能证明任意同进程恶意代码或整台机器绝对无网络。

判定：上述必要条件全部有证据则本规则离线评价通过；出现被拒动作派发、错误结论、泄密或保护触发则失败，保留输出不重试掩盖；文件缺失、关联不明或完整性不足则证据不足，不给肯定性结论。unittest OK 单独不构成完整评价。原始记录、后验计算和人工／AI 解释分别保存。

边界：不证明真实网络拦截、OS 实际发送或实际目标安全；14 项真实 HTTP 保持 PENDING_AUTHORIZATION，未派发独立证明仍 UNAVAILABLE。第二章四份文档不改，第三章本规则之外的实验不开展。
