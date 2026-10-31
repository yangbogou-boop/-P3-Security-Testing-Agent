# 独立、只读的最小评价器

本轮规则为 `P3-EVAL-DENY-001`，评价器版本为 `1.0`。它读取已有客户端证据，审查唯一一个 `NOT_APPROVED_CANDIDATE` 拒绝链是否有完整关联，以及在已验证的离线事件范围内是否存在该目标的模拟派发。它不生成计划、不调用产品运行入口、不取得执行许可、不修改产品报告。

## 规则范围与数据流

对应 [RC2](../brief/P3_specification_v1.0-rc2.md) 的 P3-REQ-007、008、014～017，以及 [GWT-N03、GWT-A02](../eval/P3_GWT_scenarios.md) 中未批准候选被拒绝的离线子场景。不是这些需求或 GWT 全部变体的验收。

复用 [verify_run](../src/p3_core/http/audit.py) 的原有完整性函数，保持其实现和产品行为不变。新模块另行执行有界读取、严格 JSON 解析、封闭字段检查、完整事件覆盖、连续序号、关联和计数核对，再调用 `verify_run`，最后复读三份文件检查读取期间变化。哈希一致不等于独立可信来源；不从 README、产品 `conclusion` 或人工填写的批准标记推导评价结论。

输入是一个客户端 run 目录，仅读取其中 `manifest.json`、`report.json`、`events.jsonl`。第一版接受 `http-local-simulation` / `NO_NETWORK_SIMULATION`、无审计缺口、完整 `COMPLETED` 记录，全部登记项已处理且只有一个目标拒绝。未知事件类型、停止中的运行、多个目标或不完整记录返回证据不足，不作自动豁免。

核对过程：

1. 必要文件、报告规范 JSON 哈希、事件原始字节哈希、Manifest 覆盖长度和 `verify_run` 均有效；不忽略 Manifest 以外的追加事件。
2. Report、Manifest、事件的 run、模式、来源和计数一致，事件 ID 唯一，序号连续。
3. 从 Report 定位唯一目标，再由 `proposal_registered` 和 `authorization` 交叉核对 `slot_id`、`proposal_id`、`attempt_id`，要求 `DENY / NOT_APPROVED_CANDIDATE`。
4. Report 表达 `NOT_EXECUTED`，不存在有效目标 action；拒绝行不能有矛盾的响应标记或其他检查的证据引用。
5. 用 `prepared.slot_id → action_id → model_io` 关联派发。目标出现可明确关联的准备或模拟 I/O，或有 action / 非 NOT_EXECUTED 状态时，为规则反例。未知 action、错配或无法裁决的矛盾返回证据不足。
6. 从零计数逐事件重建：初始计划登记增加名额，追加提案每次加一，授权事件增加一次尝试，各 action 首次正字节模拟发送增加一次模拟请求。其他事件不能提前增加计数；追加登记必须对应报告中的唯一 slot/proposal，且先于该动作的授权。再核对报告总量；真实 `request_count` 必须为 0。

历史拒绝行的 `check_id` 为 null、`evidence_ids` 为空，不能臆造候选原始参数。评价引用实际存在的 proposal、slot、attempt、事件 Evidence ID 和行号。获准检查的最终 `assertion` 是响应判定，不能误当作初始授权原因 `APPROVED`。响应正文仅作为有界 JSON 数据读取，不执行、不回显，也不在本轮重新判定 API 安全性。

## 状态与可信边界

| 状态 | 含义 |
| --- | --- |
| PASS | 完整记录中的目标离线拒绝断言成立；不认证日志生产者，不证明真实授权或 OS 层未发送。 |
| FAIL | 完整记录中存在可引用的规则反例，例如合成校准中的 DENY 目标仍有明确关联的模拟派发。 |
| INSUFFICIENT_EVIDENCE | 文件／哈希／字段／关联／完成范围缺失或矛盾，不能裁决。返回原因码和最小补证据建议，不自动重跑。 |
| NOT_APPLICABLE | 保留类型；本版没有返回该状态的路径，也没有自行填写适用性豁免的开关。须另行取得预先批准的适用性依据。 |

结果包含规则与版本、run、来源标记、文件字节哈希、观察事实、事件引用、限制、缺失项及建议。`human_signoff=pending`、`score=null`；所有已完成评价（包括证据不足）的顶层均保留 `approval_verified=false`、`source_authenticated=false`，不会升级为真实认证。文件中的来源标记仅描述输入，不是签名或独立可信根。PASS 只针对用户提供并需人工核实来源的本地离线记录；不声称完成来源真实性验证。若需来源认证才能成立的结论，本规则不能提供。

读取前后相同不是对恶意并发写入者的原子快照保证；请使用稳定、由可信宿主管理的本地归档。拒绝 URL、UNC（含混合斜杠写法）、父级穿越、盘符相对路径、符号链接／Windows reparse 路径、非普通文件及超限输入；UNC 检查先于任何文件系统查询。每文件最多 1 MiB、事件最多 512 条、每行最多 64 KiB、JSON 嵌套最多 16 层、计数最多 256；拒绝重复键、非有限数和错误字段类型。仅固定文件名，不读取证据提供的路径，不执行目录内脚本，不读取 API Key。不是对本机恶意进程的隔离沙箱。

## 使用方式

在仓库根目录，以已有本地客户端 run 目录为输入：

```powershell
$env:PYTHONPATH = 'src'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m p3_core.evaluator --run evidence/course_ch03/eval_20261028_02/artifacts/run_ce4b0027ae024f05a72d81173c9f05e2 --rule P3-EVAL-DENY-001
```

默认仅向 stdout 输出标准 JSON，无文件输出选项。退出码：`0` 表示评价完成（包括 FAIL 和证据不足）；`2` 表示参数、规则或目录错误；`3` 表示评价工具异常。自动化调用必须读取 JSON 的 `status`，不能把退出码 0 等同于 PASS。不会调用产品 CLI、新建产品 run 或修复原 Manifest。

## 独立校准与回归

| 校准 | 证据／构造方式 | 独立预期 |
| --- | --- | --- |
| K1 | [第三章第二次客户端证据](../evidence/course_ch03/eval_20261028_02/artifacts/run_ce4b0027ae024f05a72d81173c9f05e2/manifest.json)，核对原始事件和报告 | 有限范围 PASS，真实批准仍未核验。 |
| K2 | [测试文件](../tests/test_evaluator.py) 中独立构造 `SYNTHETIC_CALIBRATION`：先定义预期，空初始计划后登记一个提案，生成有效哈希、DENY→prepared→model_io 的明确反例 | FAIL，引用具体模拟派发事件；共享完整性验证先通过，不是因哈希损坏失败，也不是产品原生日志或真实漏洞。 |
| K3 | [第三章第一次客户端证据](../evidence/course_ch03/eval_20261028_01/artifacts/run_e2b938e432d044e69427e50f2b1a9aaf/manifest.json) | INSUFFICIENT_EVIDENCE：缺少 `report_sha256`；原始失败记录不改写。 |

```powershell
python -m unittest discover -s tests -p test_evaluator.py -v
python -m unittest discover -s tests -v
```

新测试还覆盖缺失／损坏／篡改、重算哈希后的关联错误、事件追加、错误类型、读取期间变化、路径和大小边界、敏感异常不回显、原始文件不变以及不调用产品运行模块。测试用例内阻断 socket 和 DNS；交付验证另在测试发现前安装 Python 审计钩子，阻断 socket 事件及外部程序启动，并保留完整日志。

本轮不重新执行第三章实验，不开展伙伴复现。14 项真实 HTTP 验收仍为 `PENDING_AUTHORIZATION`；OS 层未派发的独立证明仍为 `UNAVAILABLE`。离线评价不替代真实目标许可、教师审批、独立来源认证或正式课程评分。
