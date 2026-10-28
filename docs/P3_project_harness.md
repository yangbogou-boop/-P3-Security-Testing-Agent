# P3 Project Harness：开发 Agent 最小工作规则

2026-10-28 文档候选，待负责人审核。本文件整理已授权工作边界，不是工具层已部署的 ACL、操作系统隔离或真实测试许可证。本轮只改必要 Markdown，不运行测试、模拟实验或网络测试，不 Commit／Push。

## 两种机制不能混淆

| 机制 | 控制对象 | 权威来源／限制 |
| --- | --- | --- |
| 产品 Controller／Trusted Host | 候选动作、目标、计数、撤权、证据与 Fixture 生命周期 | RC2、可信登记及已接受架构；宿主不能绕过 Controller，技术方案不产生真实许可 |
| Project Harness | Codex 等开发 Agent 的读写、工具、验证、恢复及 Git 操作 | 当轮用户授权与工程规则；本文是可审阅说明，不声称模型已经被产品 Controller 沙箱化 |

## 权威入口、发现及冲突处理

先检查分支、HEAD、暂存／工作区和适用的 AGENTS.md，再读[Pack 索引](../review/P3_spec_harness_pack_index.md)。本次未在仓库发现 AGENTS.md；不能据此推断 Agent 无其他平台规则。

- 活动需求：[RC2](../brief/P3_specification_v1.0-rc2.md)；执行边界：[授权边界](../brief/P3_authorization_boundary.md)；审批分类：[治理登记](../brief/P3_decision_governance.md)。
- 验收定义：[GWT](../eval/P3_GWT_scenarios.md)；实现映射：[需求追踪](../eval/P3_requirement_traceability.md)。场景定义不是执行证据。
- 架构：[ADR 入口](../review/P3_architecture_summary.md)、[Supervisor 生命周期](../design/P3_supervisor_lifecycle.md)、[Trusted Host 设计](../design/P3_c3d_trusted_host_integration.md)。已接受决策与 Proposed 明确区分。
- 环境和命令：[README](../README.md)、[离线交付](P3_offline_delivery.md)；当前状态按版本化报告和实际结果判断。旧原型、带日期的历史段落不能覆盖活动规范。
- 发现冲突时记录具体条目，停止受影响操作并交负责人确认；不自行择宽、更改 RC2、提升 ADR 或虚构教师规则。任务授权不能替代目标所有者许可。

## 工具及确认边界

| 操作 | 规则 |
| --- | --- |
| 文件读取、搜索、Git status／log／diff、现有日志分析 | 当前范围允许；优先最小读取，避免输出凭据 |
| Markdown 编辑和静态链接检查 | 本轮仅必要文档；已有未知修改先保护并报告，不覆盖 |
| Python／unittest／离线 CLI | 仅在相应任务授权验证时使用；本轮不执行。静态读取／文本计算不能冒称运行验证 |
| 源码、测试、依赖、CI 修改 | 本轮禁止；后续须有对应范围授权，不擅自安装或扩大工具能力 |
| GitHub 只读查询、fetch、Commit、Push、PR | 分别按任务授权；本文不自动授予。本轮不提交、推送或改远程 |
| socket、DNS、HTTP、服务监听、真实 LLM | 本轮禁止；普通离线命令不应触发。真实 HTTP 须目标许可、教师目录与可信来源／范围绑定齐备，并另行授权执行 |
| 删除证据、清理、reset、强推、覆盖他人工作 | 不作为自动恢复手段；历史 Evidence 不动，任何破坏性事项另行人工决定 |

负责人确认普通工程取舍；重要架构决定按 ADR 流程。教师只确认有课程依据的对应事项，不为每次内部编辑新增审批。任何披露、结果或未知状态均不得由 Agent 自行改成“人工已确认”。

## 离线验证命令与证明边界

下列为仓库已有入口，供未来获准验证使用，本轮未执行。Python 3.9+，标准库，在仓库根目录 PowerShell：

```powershell
$env:PYTHONPATH = 'src'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m unittest discover -s tests -v
```

当前 278 项来自既有 CI／交付记录，不是本文新增结果。成功不代表真实网络验收。各测试中的假传输和网络阻断不能自动证明 discovery 阶段也被全局阻断；全程保护的历史外部驱动尚未形成可直接引用的仓库统一入口。后续任务若要求全程保护，必须先核对实际驱动及发现前阻断，再执行；不能把普通命令称为同等证明。

本轮文档检查使用 `git diff --check`、`git status --short` 和相对链接静态检查。未跟踪文档需额外检查内容／空白或用 `git diff --no-index` 检查，不能仅凭普通 diff 没输出认定已覆盖新增文件。

## 预算、停止与恢复

- 产品 8 项／90 秒／并发 1 是试跑值，不是开发 Agent 的时间、Token 或费用额度。容量建议也不是教师已冻结上限；不得从运行时 LLM=0 推导开发费用为 0。
- 开发额度以当轮授权范围为边界；没有明确时间／Token／费用上限时记“未设定”，不编造数值。不自动无限重试、扩大实验或启动新阶段。
- 未知改动、证据缺口、授权冲突、安全不变量冲突、非平凡修复超出范围时，停止对应工作并报告。无依据的失败不得改写成通过。
- 失败后保留命令、版本、结果及原文件；先只读定位，再提出最小修复。新运行使用新目录，不覆盖失败记录；不通过删断言、跳过测试或回滚证据使结果变绿。
- 终态不重开、未知发送不重放。实际清理／Fixture 提交遵守生命周期文档，不用手动失效标志冒充双端撤权。
- 修复需另行授权时保留现场交审核；允许修复后先针对性验证，再按任务要求全量验证。未执行步骤明确列出。

## 最小影响图与兼容边界

| 区域 | 主要影响及使用方 | 兼容／恢复边界 |
| --- | --- | --- |
| brief、GWT、ADR | 授权契约、预算及验收定义，约束全部实现 | 本轮不改；冲突交审核，不重编号 |
| p3_core controller／http | CLI、宿主、夹具依赖结构化动作和三计数 | 新入口不能绕过强制授权；本轮无接口迁移 |
| coordination／supervision／trusted_host | 登记根、sidecar、实例与 generation 生命周期 | 哈希不证明来源；缺证据禁止提交新 Fixture，不回滚已发送字节 |
| JSONL／Manifest／Report | 校验器和复核者依赖关联字段及完整性 | 历史格式保留；不通过修改旧文件补齐字段，缺失如实报告 |
| 旧 src/main.py、planner、controller 原型 | 历史演示和模拟 Token | 保留但不作为当前验收入口，不混入新版真实成本 |
| docs／review | 人工导航和工程解释 | 本轮新增四份说明，不改变程序、CI 或历史报告；有争议保留候选等待审核 |

## 交付与 Git

提交前展示实际修改范围、静态／运行验证结果及未完成事项。人工审核不由 Agent 代签。只有另行明确授权时才显式暂存批准文件、检查暂存区并 Commit；Push 单独确认授权，不使用 add .／add -A 或强推掩盖范围。保存基线和未提交工作，不自动推进下一阶段。
