# P3 开发计划与可验证任务卡

2026-10-28 文档候选，基线 `620a357bfb6c6286c10772498d3c96116703e06c`。以下 TC-01～05 均为**依据历史记录补录**，编号仅用于本次材料索引，不替代稳定 Requirement／GWT ID，不声称是开发前计划。DONE_OFFLINE 仅表示有历史离线成果，不表示完整需求验收通过。责任人统一 PENDING_OWNER_CONFIRMATION；建议角色见[责任登记](P3_ai_usage_and_responsibility.md)。本轮没有执行下列验证。

## 计划、依赖与检查点

历史顺序：需求／治理 → 核心与 HTTP 契约 → Mock 夹具 → 生命周期加固 → Trusted Host；设计与代码有交叠。当前先审核 TC-06 文档，再另行授权第三／四章证据补齐；TC-07 真实执行必须在真实许可门槛满足后安排。检查点是可审阅材料、相应测试结果及边界确认，不是累计测试数量达到某值即验收。

开始条件：输入版本和修改范围明确、无未知工作区冲突、权限满足。完成条件：本卡产出可定位、验证结果可核对、失败和限制保留、人工审核状态如实记录。一般实现不需额外教师批准；实际网络、正式契约和预算冻结按既有治理执行。

## TC-01：形成需求与架构候选

- 目标／需求：明确范围、独立授权与验收方法；P3-REQ-001～022 的规格定义，不代表全部实现。
- 输入／产出：课程资料、原型、负责人指令 → RC2、GWT、治理及 ADR。
- 模块／依赖／权限：brief、design、eval；依赖原始课程依据和范围决策，文档审核不授予测试许可。
- 验证／完成标准：每项 ID、强度、GWT 可追溯；区分授权、执行、结论；保留版本历史。
- 状态／证据：DONE_DOCUMENT_BASELINE，依据历史记录补录。[需求总结](P3_requirements_summary.md)引用 `48dd5f8`、`937c102`、`e09ca38`；[架构总结](P3_architecture_summary.md)含技术选择依据。
- 未完成：正式课程映射、契约、预算冻结及目标许可；不阻塞普通离线开发。

## TC-02：离线 Controller 与有界 HTTP 核心

- 目标／需求：独立拒绝、预算、终态、解析和有限报告；P3-REQ-003、007～017、019。
- 输入／产出：RC2、HTTP 契约 → p3_core 核心与 http 状态机、解析及审计模块。
- 模块／依赖／权限：controller、http、evidence；依赖 TC-01；只允许假传输验证，禁止真实请求。
- 验证／完成标准：[test_core](../tests/test_core.py)、[test_http_core](../tests/test_http_core.py)验证非法输入拒绝、三计数、预算、撤权、畸形响应和证据最小化；不能把假响应当 EXECUTED。
- 状态／证据：DONE_OFFLINE，依据历史记录补录；`b3a0da7`、`bd888e2`，[离线验证](../eval/P3_offline_core_validation.md)、[HTTP 核心报告](P3_http_offline_core_review.md)。
- 未完成：REQ-013 实际响应、真实 OS 发送及取消；历史通过数量不等于完整 HTTP GWT 通过。

## TC-03：可重置 Good／Known Bad 夹具

- 目标／需求：三类权限行为和合法对照；P3-REQ-004～006、014、016、018。
- 输入／产出：六项候选及权限矩阵 → Good／AUTH／BOLA／RBAC 纯业务核心与合成响应。
- 模块／依赖／权限：mock_api/core、adapter；依赖 TC-01／02；仅合成身份和内存字节，不能启动服务。
- 验证／完成标准：[test_mock_api](../tests/test_mock_api.py)核对缺陷隔离、实例重置、凭据绑定、封闭响应和解析兼容。
- 状态／证据：DONE_OFFLINE，依据历史记录补录；`e0e85d1`，[C-1 报告](P3_mock_api_c1_review.md)。
- 未完成：真实服务适配行为的集成验收；模拟结论不是实际漏洞报告。

## TC-04：撤权监督与可信证据协调

- 目标／需求：双端停止、审计失败关闭、可信登记及重置提交门槛；P3-REQ-007～012、014～018。
- 输入／产出：既有运行／服务生命周期 → Supervisor、EvidenceCoordinator、预检和验收管理清单。
- 模块／依赖／权限：supervision、coordination、preflight、acceptance；依赖 TC-02／03；可信登记来自 Controller，不能由 Planner 或人工列表冒充。
- 验证／完成标准：[C-3A/B 测试](../tests/test_c3_preflight.py)、[监督测试](../tests/test_c3_supervisor.py)、[登记测试](../tests/test_c3_registration.py)覆盖缺 sidecar、非法 action、审计标记及重置竞争；未知证据不能重置。
- 状态／证据：DONE_OFFLINE，依据历史记录补录；`3199b3f`、`767b15e`、`8e56767`，[C-3C 报告](P3_c3_supervisor_review.md)及[生命周期](../design/P3_supervisor_lifecycle.md)。12 种竞态为历史交付记录，本轮未复跑。
- 未完成：真实可信来源、OS 竞态和资源关闭验收；未派发独立证明 UNAVAILABLE。

## TC-05：可信宿主离线集成与策略比较切片

- 目标／需求：连接已有组件并保留有限结论；P3-REQ-003、007、014～021。
- 输入／产出：可信离线运行、夹具和证据接口 → Trusted Host 九组演示及 fixed／dynamic 模拟比较。
- 模块／依赖／权限：trusted_host、experiments、http/strategies、delivery；宿主依赖 TC-04；策略切片历史上先于 TC-04，二者不是同一次实验。只允许离线模拟。
- 验证／完成标准：[test_c3d_host](../tests/test_c3d_host.py)、[test_remaining](../tests/test_remaining.py)；绑定错误拒绝、证据不完整停止、两策略条件一致、模拟／真实计数分开。
- 状态／证据：PARTIAL，依据历史记录补录；策略 `0ab1dd5`／`30c98db`，宿主 `b79a4e3`／`c3ea320`；[36 次结果](../eval/P3_offline_strategy_results.json)、[C-3D 报告](P3_c3d_implementation_review.md)。离线部分已有结果，不等于 REQ-021 全部完成。
- 未完成：原始记录交付与执行版本绑定、准备／人工成本、伙伴复现、真实比较；[ADR-005](../design/ADR_005_deterministic_strategy_comparison.md)仍 Proposed。本轮不开展实验。

## TC-06：第二章 Pack 与责任整理

- 目标／需求：为 P3-REQ-001～022 建立文档导航和开发约束，不新增产品要求。
- 输入／产出：历史 Git、阶段报告、课程审计 → [映射索引](P3_spec_harness_pack_index.md)、本卡组、[Harness](../docs/P3_project_harness.md)、[AI 与责任登记](P3_ai_usage_and_responsibility.md)。
- 模块／依赖／权限：仅 docs／review Markdown；依赖 TC-01～05 的已有记录；本轮只读源码，不执行测试或实验。
- 验证／完成标准：相对链接存在、diff 无空白错误、仅批准文档变化、保护文件不变；负责人审核后才视作文档交付接受。
- 状态：TODO（候选已整理，等待审核）；未知责任人、披露完整性和教师适用范围不能靠 Agent 自动确认。

## TC-07：真实集成与正式验收前置准备

- 目标／需求：在独立许可满足后验证真实行为；P3-REQ-001、002、010～018、020、021。
- 输入／产出：目标许可、教师目录、范围／版本／实例绑定 → 可审核的执行计划及未来真实证据。本卡不发起执行。
- 模块／依赖／权限：live、service、Supervisor 及[14 项验收清单](../eval/P3_c3_acceptance_manifest.json)；依赖 TC-04／05 和真实来源核验。
- 验证／完成标准：逐项收集实际发送、撤权、关闭及完整响应证据，独立核验；具体标准沿用[授权检查表](../eval/P3_c3_authorization_checklist.md)。
- 状态：BLOCKED／PENDING_AUTHORIZATION；许可与教师目录尚未落实，禁止监听、连接和真实 HTTP。正式验收不能由离线 CI 或技术 ADR 代替。
