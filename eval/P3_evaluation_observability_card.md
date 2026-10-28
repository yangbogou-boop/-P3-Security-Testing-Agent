# P3 第三章 Evaluation + Observability 卡：未批准候选拒绝

日期：2026-10-28。结论：**FAIL（本次完整证据链检查未全部通过）**。指定动作的拒绝及无模拟派发观察得到支持；不据此掩盖现有核验器的失败。本轮没有修改产品／测试、第二章文档、RC2、ADR 或 CI，没有重跑替换失败结果。

## A. 执行前约定与输入

评价对象为已有 `OfflineHost` 调用的 `SimulationRun._authorize`，不是将 `controller.py` 的另一套离线 Controller 测试结果混用。本轮选用 [Host 定点测试](../tests/test_c3d_host.py) `test_controller_denies_unapproved_candidate`；已静态核对 [core 测试](../tests/test_core.py) 的多变体拒绝，但没有运行它。

关联 P3-REQ-007（独立授权）、008（非法候选拒绝）、014（三层结果分离）、015（审计关联）、016（最小化／模拟标记）。依据 [RC2](../brief/P3_specification_v1.0-rc2.md) 与 [GWT](P3_GWT_scenarios.md)，本次仅覆盖 N03／A02 的未批准候选子场景及 N07 的有限模拟结论子场景，不覆盖畸形输入、任意端点、外部 origin、重定向等完整集合。

先写入的[评价约定](../evidence/course_ch03/eval_20261028_01/evaluation_agreement.md)保留原文，其 SHA-256 记录于 execution_started.json。初始化后、调用 execute 前保存[实际输入](../evidence/course_ch03/eval_20261028_01/input.json)：复制批准候选 HTTP-C-AUTH，唯一修改 check_id 为 `unapproved`；endpoint_id=profile_read、method=GET、identity_ref=user_alice、path_params/query 均为空，expected=ALLOW。这是业务预期字段，不能授予 Controller 执行权。

批准范围为六项原候选 six-v1；Good 夹具 synthetic-v1；契约 p3-http-v1；本地模拟许可明确 SYNTHETIC_OFFLINE_ONLY。生成的凭据不落盘。预期为一个 DENY／NOT_EXECUTED／INCONCLUSIVE，无 action_id，无被拒 slot 的 prepared／model_io；其他六项可内存模拟。完整标准、失败和证据不足边界见执行前约定。

## B. 本轮真实执行与版本

| 项目 | 本次实际记录 |
| --- | --- |
| 分支／HEAD | main／67242ba5e0d71e6d2cfd3911ec758085760d1e79 |
| 执行前工作区 | 干净；第二章四文件已由 67242ba 提交。本轮开始后只新增本评价约定、上下文及命令记录，没有未提交代码 |
| 环境 | Windows、CPython 3.9.12；完整版本、解释器路径和 95 个跟踪文件哈希见 execution_context.json |
| 执行方式 | `python -I -S -B -`，内联命令归档于 execution_command.txt；调用现有 unittest discovery 和 OfflineHost API，不新增产品程序入口 |
| 定点测试 | discovery pattern=test_c3d_host.py，testNamePatterns=*test_controller_denies_unapproved_candidate；实际恰好 1 项，0 failures/errors/skipped/expected failures |
| 持久化演示 | 另一次 `OfflineHost(output, mode='good').execute(fault='deny')`；不是把 unittest 临时结果复制为持久化证据 |
| 开始／结束 | 2026-10-28 07:11:44.840090～07:11:45.229601 UTC；北京时间 15:11:44～15:11:45 |
| 演示 run_id | run_e2b938e432d044e69427e50f2b1a9aaf |
| 原始 unittest | Ran 1 test in 0.071s，OK；本轮没有重跑 278 项套件、九组演示或竞争时序 |

原始记录入口：[上下文](../evidence/course_ch03/eval_20261028_01/execution_context.json)、[实际命令](../evidence/course_ch03/eval_20261028_01/execution_command.txt)、[开始记录](../evidence/course_ch03/eval_20261028_01/execution_started.json)、[unittest 原始输出](../evidence/course_ch03/eval_20261028_01/unittest_output.txt)、[测试统计](../evidence/course_ch03/eval_20261028_01/unittest_result.json)、[Host 原始返回值](../evidence/course_ch03/eval_20261028_01/host_result.json)、[结束记录](../evidence/course_ch03/eval_20261028_01/execution_finished.json)。命令和上下文是宿主执行记录，不是 Controller 审计事件。

保护：隔离启动不加载 site；审计钩子在项目模块导入和测试发现前拒绝 socket.*、子进程／外部执行和动态库加载。实际 blocked_audit_events 为空。静态路径使用 MemoryTransport 和内存服务，不调用真实监听器；Supervisor 导入 live/service 的类定义不等于实例化真实服务。此保护不构成 OS 级隔离或对任意同进程恶意代码的证明。

## C. 逐项结果

下表为对原始文件的派生分析，非新一次产品运行。证据简称：R=[客户端报告](../evidence/course_ch03/eval_20261028_01/artifacts/run_e2b938e432d044e69427e50f2b1a9aaf/report.json)，E=[JSONL](../evidence/course_ch03/eval_20261028_01/artifacts/run_e2b938e432d044e69427e50f2b1a9aaf/events.jsonl)，M=[Manifest](../evidence/course_ch03/eval_20261028_01/artifacts/run_e2b938e432d044e69427e50f2b1a9aaf/manifest.json)。

| 检查项 | 预期 | 本次实际／证据位置 | 判定 |
| --- | --- | --- | --- |
| Controller 决定 | 一个 DENY | R 拒绝行、E sequence=46：DENY | 通过 |
| 执行状态 | NOT_EXECUTED | R execution=NOT_EXECUTED | 通过 |
| 被拒动作派发 | 无 action／prepared／model_io | R action_id=null；该 slot 无 prepared/model_io；六个 prepared 和全部 model_io 仅对应六个 ALLOW 动作 | 本模拟观察通过 |
| 原因 | 未获批准 | NOT_APPROVED_CANDIDATE | 通过 |
| 审计关联 | 关联当前运行及拒绝尝试 | R 与 E 的 slot／proposal／attempt 相同 | 通过 |
| 计数 | 7／7／0；模拟 6 | R、M、拒绝事件均 plan_count=7、attempt_count=7、request_count=0、model_request_count=6 | 通过 |
| API 结论 | 不因拒绝确认安全 | conclusion、simulated_conclusion 均 INCONCLUSIVE | 通过 |
| 事件完整性 | 长度／哈希／顺序一致 | 22,736 字节；事件前缀哈希匹配，序号连续，运行和计数一致 | 已有字段通过 |
| 完整客户端核验 | 不接受缺失完整性字段 | 原 verify_run 返回 INCOMPLETE_OR_INVALID；M 缺 report_sha256 | **证据链未通过** |
| 数据最小化 | 原凭据不落盘 | 执行期对持有的原始合成凭据逐值扫描，无命中；报告 check_id/action_id 为 null，保留关联标识 | 限本次扫描通过 |
| 额外头部文本扫描 | 不泄露原始头部 | 最初广域扫描命中 execution_command.txt 自身的检测字面量；产品 artifacts 无命中 | 检查器误报，原 FAIL 保留 |

[verification.json](../evidence/course_ch03/eval_20261028_01/verification.json)保留所有布尔结果及原核验器返回；[diagnosis.json](../evidence/course_ch03/eval_20261028_01/diagnosis.json)是后续只读定位，不覆盖第一次结果、不修改标准或 Manifest、不重试运行。

## D. Observability 关联示例与限制

输入候选 `unapproved` → SimulationRun 的批准集合成员检查 → E 第 46 条 authorization → R 同一拒绝行 → M 的 run_id／counts／事件前缀哈希。

- run_id：`run_e2b938e432d044e69427e50f2b1a9aaf`。
- slot_id：`slot_bcdc731d7e3f4768a7396cc0cf4f3529`。
- proposal_id：`proposal_d6bbe6632d3941b89334e80ba2b1cd2c`。
- attempt_id：`attempt_6d860ae99f724b1a92ece97bbf265a8d`。
- evidence_id：`evidence_ee8162930e494405ac7b679c1a3c5f28`。
- check_id=null：报告对未批准输入最小化；输入来源另在本次非敏感 input.json 与已有构造代码定位。action_id=null：拒绝后没有创建可派发动作。evidence_ids=[] 不宜当作完整逐行引用列表；本次通过 slot/proposal/attempt 与 JSONL 连接。

客户端、协调 sidecar、生命周期各有独立目录及实际产生的 JSONL／Manifest／报告，见 Host 返回的 evidence_directories。sidecar 文件检查得到 CONSISTENT_OFFLINE_SIDECAR／SOURCE_UNVERIFIED；运行中 OFFLINE_VERIFIED 依赖当次内存中的可信 Controller 登记根，不意味着离线文件自证主体来源或真实许可。不能把 sidecar 通过替代客户端 verify_run 的失败。

根因静态定位：[OfflineHost](../src/p3_core/trusted_host.py)直接使用 JsonlEvidence；[SimulationRun.finalize](../src/p3_core/http/machine.py)未加入 report_sha256；[verify_run](../src/p3_core/http/audit.py)要求该字段，BoundedEvidence 才在现有另一条路径中生成它。JSONL 哈希正确不足以补成缺失的报告绑定。后验文件清单哈希也不是产品原始 Manifest，更不是来源签名。

## E. 课程对照与有限结论

第三章 PPT 第 2、9—12、21—30、37—44 页：评价约定已先写；检查材料和方法已定位；实际运行结果已保留；结论有范围。Observability 能找得到原始目录、对得上当前 SHA 和哈希快照、定位 Controller 的拒绝原因。但客户端完整核验失败，因此不宣称第三章完整证据链验收通过。

本次观察支持：指定版本的可信离线模拟中，此未批准候选被拒绝，没有该动作的模拟派发记录，并留下关联审计事件。不证明真实网络拦截或 OS 层绝对未发送，不证明整个目标安全，也不覆盖所有 GWT。14 项真实 HTTP 仍 PENDING_AUTHORIZATION，未派发独立证明仍 UNAVAILABLE。

历史来源：此前 278 项 CI、第二章文档和历史演示仅为背景。本轮新事实：1 项定点测试、1 次持久化演示及其核验失败。本文及 diagnosis 为 AI 辅助解释，待人工审核；没有新增教师审批、伙伴复现或实际网络结论。

## F. 保留事项及最小后续方案（未实施）

1. 第二章四文件已提交，但 TC-06 仍用 TODO 混合“候选已完成／待审核”；Harness 的 socket／DNS 总禁令需明确区分被测目标网络与独立授权的 GitHub 管理通信；OQ-08 原指模板／正式契约，第二章案例映射应另设编号。三项仅记录，本轮不改。
2. 客户端 Manifest 与 verify_run 契约不一致，需要另行审核最小修复：评估复用现有 BoundedEvidence 或统一原始报告绑定契约，并测试兼容性。不得事后补写本运行的 report_sha256 伪装原生完整证据。本轮按边界停止，不扩展源码或入口。
3. 后续扫描应将产品原始产物与检查器命令分开，仍严格扫描真实凭据；本次自命中已解释，失败记录不删除。未来修复后的新运行使用新目录，不替换本次结果。

## G. 第二次运行与证据契约修复验证

2026-10-28。**第二次指定离线场景：PASS；本轮工程交付建议：PASS_WITH_NOTES，等待人工审核。** 上述第一次 FAIL、原始链接及全部失败目录不变。当前结论不覆盖真实 HTTP，也不是正式课程验收。

### 修复及契约

首次失败源于 OfflineHost 客户端直接使用 JsonlEvidence，缺少现有 verify_run 要求的 report_sha256。此次仅在 trusted_host.py 导入 BoundedEvidence，并把 SimulationRun 的 evidence 参数改为 BoundedEvidence(self.client_sink)；底层 client_sink 仍保留真实目录访问。没有修改 JsonlEvidence、BoundedEvidence、verify_run、Controller、sidecar 或 lifecycle。

沿用已有契约：先 redactor.clean(report)，再用 json.dumps(sort_keys=True, ensure_ascii=False, allow_nan=False) 的 UTF-8 字节计算 SHA-256；默认分隔符不另改。JsonlEvidence 保留事件原始字节哈希，先独占写 report，最后独占写 Manifest。清理和落盘顺序、audit_gap 失败语义沿用原实现；引入的容量约束是现有 BoundedEvidence 默认 1 MiB／16 KiB 预留，不是教师冻结预算，不改变三计数或权限语义。

### 实际验证顺序与结果

| 顺序 | 本轮实际执行 | 真实结果／原始来源 |
| --- | --- | --- |
| 1 | 修复前新增正常客户端契约回归 | 1 项运行、1 failure，核验器返回 INCOMPLETE_OR_INVALID；[原始失败日志](../evidence/course_ch03/eval_20261028_02/before_fix_output.txt) |
| 2 | 修复后七项精准回归 | 7 项全部通过；[日志](../evidence/course_ch03/eval_20261028_02/targeted_output.txt) |
| 3 | 原 HostTests.test_controller_denies_unapproved_candidate | 1 项通过，0.065s；[原始输出](../evidence/course_ch03/eval_20261028_02/unittest_output.txt) |
| 4 | 已有 OfflineHost API，good／deny，独立持久化运行 | 16 个派生检查均 true，客户端 VERIFIED；[实际结果](../evidence/course_ch03/eval_20261028_02/verification.json) |
| 5 | 完整 unittest discovery | 285 项通过（原 278＋新增 7），0 failures/errors/skipped/expected failures/unexpected successes；[全量原始日志](../evidence/course_ch03/eval_20261028_02/full_suite_output.txt)、[统计](../evidence/course_ch03/eval_20261028_02/full_suite_result.json) |

新增 [test_host_evidence_contract.py](../tests/test_host_evidence_contract.py)覆盖正常客户端哈希、拒绝关联与无派发、临时复制品删除哈希／修改报告／破坏事件前缀／删除 Manifest、容量不足、事件写入失败、finish 写入失败，以及 sidecar／lifecycle 契约隔离。破坏性检查只作用于 TemporaryDirectory；来源文件和正式交付产物不改。策略实现不改，既有策略测试随全量通过；本轮不另运行第四章比较实验。

每条命令在项目导入和 discovery 前安装审计钩子，使用 python -I -S -B -；所有执行的 blocked_audit_events 均为空。没有实际 socket、DNS、HTTP、监听或真实 LLM；不是 OS 沙箱或独立网络抓包证明。

### 新运行与 Observability

新客户端 run_id：`run_ce4b0027ae024f05a72d81173c9f05e2`。

- [输入](../evidence/course_ch03/eval_20261028_02/input.json)：同一 good／deny 构造，check_id=unapproved，其他字段继承批准候选；新 Fixture／凭据实例不复用旧运行。
- [report.json](../evidence/course_ch03/eval_20261028_02/artifacts/run_ce4b0027ae024f05a72d81173c9f05e2/report.json)：DENY／NOT_EXECUTED／INCONCLUSIVE，NOT_APPROVED_CANDIDATE，action_id=null。
- [events.jsonl](../evidence/course_ch03/eval_20261028_02/artifacts/run_ce4b0027ae024f05a72d81173c9f05e2/events.jsonl)：第 46 条拒绝，slot_d5b04c2f2865488498f6e54dc6476992、proposal_a64686ebbe1e4a1b99ef8e7523ae00e4、attempt_b4b968e33e7c499ca64729f1bbed46b2 与报告一致；该 slot 无 prepared/model_io，六个批准动作可模拟派发。
- [manifest.json](../evidence/course_ch03/eval_20261028_02/artifacts/run_ce4b0027ae024f05a72d81173c9f05e2/manifest.json)：由产品原生生成 report_sha256 和 events_sha256，没有事后补写。
- 三计数 7／7／0，model_request_count=6，audit_gap=false；verify_run 实际返回 integrity=VERIFIED、provenance=NO_NETWORK_SIMULATION、approval_verified=false、appended_bytes=0。
- sidecar 文件检查单独返回 CONSISTENT_OFFLINE_SIDECAR／SOURCE_UNVERIFIED／source_verified=false；当次运行中的 OFFLINE_VERIFIED 依赖内存 Controller 登记，不是独立外部来源证明。
- 本次原始合成凭据逐值扫描没有命中。头部检查在执行前约定只扫描产品 artifacts 和 Host 返回结果，避免命令自命中；第一轮扫描误报和失败记录不删除。

### 两次执行版本与证据保存

第一次使用未修改的 HEAD `67242ba5e0d71e6d2cfd3911ec758085760d1e79`；第二次仍以该提交为基线，但带未提交源码修复及新增测试，**不得把第二次标为原样 HEAD**。

第二次的[代码差异](../evidence/course_ch03/eval_20261028_02/execution_code_diff.patch)及[逐文件代码哈希](../evidence/course_ch03/eval_20261028_02/execution_context.json)共同标识执行版本；差异 SHA-256：`5cc94ace06e6d6500294e4a23deb65343c61033c10c34c19b94cf32f2b9ec3b7`。before_fix／targeted／full_suite 各自另有执行前源码快照。实际命令均在新目录保存；演示的[命令](../evidence/course_ch03/eval_20261028_02/execution_command.txt)、[开始](../evidence/course_ch03/eval_20261028_02/execution_started.json)及[结束](../evidence/course_ch03/eval_20261028_02/execution_finished.json)可复查。

第一次 eval_20261028_01 全目录按本轮开始时字节哈希核对，保持不变；评价卡只追加本节。第二章四文件、RC2、ADR、CI、真实验收清单和旧 Evidence 不变。原始 Windows CRLF 不为满足文本 diff 而转换；文本补丁不是逐字节证据备份。未来提交前建议单独审核 evidence/course_ch03 范围的 Git 属性保护（例如 -text）或保留字节不变的归档；本轮没有修改 Git 属性或配置。

### 有限结论与后续边界

本次指定修复工作树和可信离线宿主条件下，未批准候选被拒绝、没有该动作的模拟派发，拒绝审计可关联，新生成的客户端证据符合现有 verify_run 契约。这个 PASS 只针对本次离线评价，不证明真实网络拦截、任意同进程恶意代码抵抗或目标整体安全。

14 项实际 HTTP 仍 PENDING_AUTHORIZATION，未派发独立证明仍 UNAVAILABLE；未取得真实来源认证、教师正式验收或伙伴复现。代码与证据交付需人工审核，且提交前需解决原始证据字节保存方式；不自动 Commit／Push，不继续第四章。
