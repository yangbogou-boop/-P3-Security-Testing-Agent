# P3 第二章课程作业完整性核查

核查日期：2026-11-04。基线：main，HEAD `5a6e81a273be104f8703be984eba929334b18d9e`（本地与 origin/main 一致）。本轮只读核查，未运行测试、实验或真实 HTTP。

## 状态口径（四类，互不替代）

- **文档内容具备**：对应文档／章节存在且信息完整。
- **实际测试完成**：相应离线／真实测试已执行并保留证据。
- **同行审查完成**：真实外部同学已完成审查并签署。
- **老师验收确认**：老师已确认适用范围／等价交付。

“文档内容具备”不等于“实际测试完成”，更不等于“同行审查完成”或“老师验收确认”。四类状态分别记录，不得互相升级。

## 10 项交付内容核查表

| # | 课程要求 | 对应材料 | 文档内容 | 实际测试 | 同行审查 | 老师验收 |
|---|---|---|---|---|---|---|
| 1 | Problem Frame | `brief/P3_problem_frame.md`（用户/场景、两层权限、目标非目标、INV-01～05、角色） | 具备 | —（文档项） | 未完成 | 待确认 |
| 2 | Goal / Non-goal / Scope / Invariants | `brief/P3_problem_frame.md` §1／§3／§4 | 具备 | — | 未完成 | 待确认 |
| 3 | Facts / Assumptions / Decisions / Open Questions | Facts→RC2 §2；Assumptions→`review/P3_ai_usage_and_responsibility.md` AS-01～05；Decisions→ADR-001～005；OQ→RC2 §9 OQ-01～08 | 具备 | — | 未完成 | 待确认 |
| 4 | ≥6 条稳定 ID 需求 | `brief/P3_specification_v1.0-rc2.md` §6 P3-REQ-001～022（22 条） | 具备 | 离线子场景部分 | 未完成 | 待确认 |
| 5 | ≥2 正／2 负／2 对抗 GWT | `eval/P3_GWT_scenarios.md`（P01～P05、N01～N07、A01～A04 及子变体） | 具备 | 离线子场景部分；真实 HTTP 未执行 | 未完成 | 待确认 |
| 6 | 一张状态图或 Impact Map | 状态：`design/P3_http_integration_design.md` §2 mermaid + §5 action 阶段 + RC2 §5；Impact Map：`docs/P3_project_harness.md` §最小影响图 | 具备 | — | 未完成 | 待确认 |
| 7 | 一张 Acceptance Matrix | `eval/P3_requirement_traceability.md`（REQ↔GWT↔测试映射） | 基本具备 | 离线映射已有；完整 HTTP 未完成 | 未完成 | 待确认 |
| 8 | 一份 Plan + 5～8 个 Tasks | `review/P3_development_task_cards.md`（TC-01～07，7 张） | 具备（历史补录） | — | 未完成 | 待确认 |
| 9 | 一份 Repository Map | [README 文档导航](../README.md#文档导航) + [总索引按任务查找](../docs/INDEX.md#按任务查找) + [根 AGENTS.md 开发导航与模块定位](../AGENTS.md#开发导航与模块定位) + [Pack 索引](P3_spec_harness_pack_index.md) | 具备 | — | 未完成 | 待确认 |
| 10 | Validation Commands / Permissions / Stop-Ask-Rollback | 命令→`README.md`／`AGENTS.md`；权限→`docs/P3_project_harness.md`；停止恢复→`AGENTS.md`／harness | 具备 | — | 未完成 | 待确认 |

## 关键口径说明（本核查采用）

1. **Acceptance Matrix（#7）**：规格↔GWT↔测试映射**基本具备**（`eval/P3_requirement_traceability.md`），完整 HTTP 验收未完成。**真实 HTTP 实验不是完成第二章文档的自动前置条件**；文档完整性按“映射是否具备”判断，真实执行单列为待授权项，不因此判定第二章文档缺失。
2. **Task Cards（#8）**：7 张已具备，明确其“历史补录”属性，**不伪造事前计划**；**不自动将 TC-06 或 TC-07 标记 DONE**（TC-06 仍 TODO，TC-07 仍 BLOCKED／PENDING_AUTHORIZATION）。
3. 四类状态（文档内容具备／实际测试完成／同行审查完成／老师验收确认）分别记录，见上表，不得互相升级。

## 三项单独核查

| 项 | 状态 | 说明 |
|---|---|---|
| Peer Review（真实外部同学审查） | 未完成 `NOT_YET_REPRODUCED_BY_PEER` | 无真实同学审查记录／签名／日期 |
| Teacher Gate（老师实际确认） | 未完成 `NEEDS_TEACHER_CONFIRMATION` | E 卡四问未发送、未答复 |
| PaperManagement-Lab 与 P3 等价 | 待老师确认 | 12 项映射已备（`review/P3_spec_harness_pack_index.md`），适用范围 `NEEDS_TEACHER_CONFIRMATION` |

## 仍需补充 / 需真实人员完成

1. 文档层（本人可做）：Acceptance Matrix 逐项执行版本与原始证据归档补全；TC-06 审核签署；责任归属确认。
2. 老师确认（Teacher Gate）：离线模拟范围、纯确定性评价 Agent、PaperManagement-Lab 等价、第一章作业回执。
3. P1 实际执行（Peer Review）：第二章 Specification Pack 规格审查（审查表见 `P1_ch02_spec_review_template.md`，交付目录）。
4. 真实 HTTP：14 项仍 `PENDING_AUTHORIZATION`，需目标许可 + 教师目录 + 版本绑定 + 可信夹具监督齐备。

## 结论

第二章“文档类”10 项交付物 P3 已基本齐备（8 项完整、2 项局部）；但 Peer Review、Teacher Gate、PaperManagement-Lab 等价确认三项真人签名事项均未发生，是第二章剩余缺口，不能由文档补录替代。
