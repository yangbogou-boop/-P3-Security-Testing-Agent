# 项目参考自评（独立评分层）

P3-SELF-ASSESSMENT-001 v0.1由负责人批准为自定义参考标准，九维度总权重100，非教师正式成绩、非系统安全百分比。Rubric常量位于self_assessment.py，canonical JSON的SHA-256为a2fdbca9371fb22c3ccf3336e9647b46153a35e65da581751f61ea949ab42ab8。更改权重会改变哈希，旧索引不能沿用。

不更改evaluator.py的DENY/BUDGET/REVOKE接口，原score=null保留。此模块是内容核查记录的确定性计算与引用校验器，不声称能自动理解所有Markdown或认证人工能力。实际内容判断者必须在reviewer_kind中披露；本次为Codex AI，不是独立人类审核。

## 输入与执行

```text
python -m p3_core.self_assessment --index <已核查证据索引> --index-sha256 <独立固定的索引哈希> --target-commit <目标SHA> --format json
python -m p3_core.self_assessment --index <同一索引> --index-sha256 <同一哈希> --target-commit <同一SHA> --format text
```

先设置PYTHONPATH=src。模块只输出stdout；保存时使用独立新目录，不能覆盖原证据。退出0表示报告生成，不能理解为全部达标；输入、固定哈希或读取变化错误退出2。建议在导入前采用项目已有无网络、禁子进程保护方式。

每个固定条件记录MET、NOT_MET或UNVERIFIED、理由与文件引用。引用含完整路径、SHA-256、实际原文片段、内容观察、目标版本、证据版本及历史限制。机器核对引用字节与原文，读取前后复核；不因文件存在就给分。错误版本、错误哈希、虚构片段或缺件降为UNVERIFIED。证据生产者不能通过README更改Rubric；调用者必须在审查索引后独立固定索引哈希。自行计算哈希不是来源认证，模块不能防御恶意宿主同时改写输入和信任参数。

MET给该条件分；NOT_MET给0但计入已判定权重；UNVERIFIED得分null、计入待核验权重。已核实得分为MET和，区间上限为其加待核验权重；有待核验项时完整总分null，不归一化。报告同时展示earned=0与score=null，前者仅为已获得的合计，不将未知当已判0分。

v0.1不提供从自填JSON认证人类签名的入口；个人25分、本人复核、P1活动等人工条件强制待核验。本版无法单靠自动运行得到完整100分结论。后续若接收真实人工确认，须独立审核来源与适用条件，不用普通开关绕过；本次已批准的范围不要求伪造完成状态。

## 实际运行

2026-11-06仓库外原始报告位于D:/codex/P3_final_delivery_pack_20261102/P3_self_assessment_20261106。目标基线5a6e81a273be104f8703be984eba929334b18d9e；评分模块为未提交新增文件，执行记录另绑定其源码哈希。索引中的本轮测试是工作区测试，不冒充该历史commit内已有评分器。

报告由58分已获得、60分已判定权重、40分待核验组成；区间58～98，完整总分null。历史实验代码/环境未完整绑定明确不满足2分，其余未完成的人工核查仍待核验。所有分数均为已固定AI内容核查的参考结果，不是独立人工认证。
