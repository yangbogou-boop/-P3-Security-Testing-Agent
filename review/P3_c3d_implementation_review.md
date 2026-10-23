# C-3D 离线可信宿主集成审核材料

日期：2026-10-23。基线：8e56767b1840c5e5626302ebdabdc8020c216bc6，分支 main。候选实现尚未提交，等待人工审核。真实 HTTP 验收仍为 PENDING_AUTHORIZATION。

## 实际交付

本轮仅新增五个文件，所有 82 个原有文件哈希保持一致：

- [trusted_host.py](../src/p3_core/trusted_host.py)：最小离线宿主、单次执行入口、内存传输与生命周期适配器、模块命令行。
- [test_c3d_host.py](../tests/test_c3d_host.py)：20 项确定性无网络测试。
- [集成设计](../design/P3_c3d_trusted_host_integration.md)：数据流、职责、接口与未派发证明限制。
- [演示计划](../eval/P3_c3d_offline_demo_plan.md)：九组场景与运行方式、需求映射。
- 本审核报告。

复用 SimulationRun 的 Controller、现有固定配置与明确 synthetic 的 registry、FixtureManager、ServiceAdapter、EvidenceCoordinator 和 Supervisor。没有新许可体系，没有修改 AuthorizedService 或 LocalRegistry，也未通过替换真实许可来调用服务端真实执行路径。

## 验证结果

标准命令与全程网络入口阻断驱动均执行完整 unittest：**278 项全部通过，原 258 项保留，新增 20 项**。无 skipped、expected failure 或 unexpected success。新增测试首轮 18 项全部通过，再补宿主并发入口与无 sidecar 的完整流程两项，合计 20 项；没有通过删测试、降低断言或修改原实现取得通过。

```powershell
$env:PYTHONPATH = 'src'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m unittest discover -s tests -v
```

全程保护驱动在发现测试之前即替换 socket、create_connection、getaddrinfo、gethostbyname、gethostbyname_ex 为抛错入口；同样保护离线演示。测试使用内存字节交付，未创建真实 socket 或监听器。原独立审核的 12 种 Fixture 提交／失败通知时序重跑全部通过，创建次数、提交次数与先后顺序断言保留。

| 实际演示 | 模型请求数 | 真实请求数 | sidecar / Supervisor |
| --- | --- | --- | --- |
| Good | 6 | 0 | OFFLINE_VERIFIED / RETIRED |
| AUTH | 6 | 0 | OFFLINE_VERIFIED / RETIRED；AUTH 检查模拟 FAIL |
| BOLA | 6 | 0 | OFFLINE_VERIFIED / RETIRED；BOLA 检查模拟 FAIL |
| RBAC | 6 | 0 | OFFLINE_VERIFIED / RETIRED；RBAC 检查模拟 FAIL |
| Controller DENY | 6 | 0 | 拒绝另占一次登记和尝试，共 7；无 action，不制造连接摘要 |
| sidecar 审计失败 | 1 | 0 | AUDIT_FAILED / FAILED，停止后续动作 |
| 摘要缺失 | 6 | 0 | EVIDENCE_INCOMPLETE / FAILED |
| 首写前撤权 | 0 | 0 | EVIDENCE_INCOMPLETE / FAILED |
| 部分发送后撤权 | 1 | 0 | EVIDENCE_INCOMPLETE / FAILED |

Good 的六项模拟结论为 PASS；三种缺陷只确认对应模拟 FAIL。所有实际 execution 保持 NOT_EXECUTED、API conclusion 保持 INCONCLUSIVE。RETIRED 仅表示旧生命周期已完成允许的一次离线 Fixture 切换，不表示通过真实安全验收。

## 未派发证明的结论

本轮完成分类与保守处理，未实现可放宽证据门槛的未派发证明。Controller 明确拒绝可从其授权结果与无 action 区分；已批准但模型尚未发送仅报告 NO_MODEL_SEND_OBSERVED。审计失败为 UNKNOWN，部分发送不得解释为未执行。报告明确 nondispatch_proof=UNAVAILABLE。

现有接口缺少独立可信、不可重开的动作终态未派发证明及其完整审计契约。缺失服务摘要不能替代该证明。用户允许保留 EVIDENCE_INCOMPLETE 的分支因此继续适用；不能为了完整演示伪造摘要或新增人工豁免。需要后续人工决定是否设计这一证明接口，当前不改 Controller 的授权、预算或终态语义。

## 安全边界及残余风险

宿主入口不接收任意目标、许可、凭据或网络执行开关；Planner 仍只能提出候选，最终 ALLOW/DENY 来自原 Controller。模拟服务摘要来源为内存适配器的实际交付观察，不是来自真实 AuthorizedService 的网络证据。运行、实例、scope、版本和起始代次固定，旧宿主及旧凭据不能参与新运行。

可信 Python 宿主是信任边界，不抵御任意同进程代码修改私有成员。宿主使用少量已有私有观察字段，未来接口变更需要回归审查。最后报告写入失败发生在 Fixture 提交之后时，保留提交事实并停止，不能保证失败文件完整存在；返回报告会清除新实例可用性，不宣称回滚。

RC2、ADR-001～005（005 仍 Proposed）、Controller、CI、历史 Evidence 和两份真实验收状态文件均未修改。此前获授权删除的三份旧 Evidence 在开始时已不存在，本轮没有执行删除。14 项真实 HTTP 用例仍待授权。

真实集成尚缺目标所有者或正式受托者许可、教师目标／测试目录、可信核验来源、实际实例及凭据绑定、预算和撤权责任记录、故障注入范围许可。真实 OS 调度、监听器、网络超时／撤权、双端来源认证及正式课程验收未执行。

## 交付材料与审核重点

任务输出目录：`D:\codex\2026-10-12\referenced-chatgpt-conversation-this-is-an\outputs\c3d`。

- `standard.log`、`guarded.log`：两次完整测试日志。
- `offline-demos.json`、`demo-evidence/`：九组明确标注模拟来源的报告及 UUID 目录证据；未写入仓库历史 Evidence。
- `reset-races.json`：原 12 种时序结果。
- `validation.json`：基线文件、语法、链接、验收状态与 Git 范围检查。
- `P3-c3d-review.diff`：包括全部五个新增文件的完整差异。

请重点审核内存服务端摘要来源、单次宿主入口、私有观察字段的使用、未派发证明不放宽门槛，以及提交后审计失败保留事实的处理。建议批准后使用 `feat: integrate trusted offline host lifecycle`，本轮不执行 Commit、Push 或进入下一阶段。
