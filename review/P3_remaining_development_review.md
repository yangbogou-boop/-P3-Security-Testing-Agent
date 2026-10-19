# P3 剩余工程开发交付／人工审核报告

日期：2026-10-19。基线：`e0e85d1`。状态：**等待人工代码审核；没有 Commit、Push 或正式课程验收。**

## 1. 范围与工作区保护

实际 Git 仓库为 `D:\project\-P3-Security-Testing-Agent`；用户输入的无中间分隔符路径是先前导出文件的位置，不是本次源码仓库。开始时 main 与本地 origin/main 引用一致；本轮未进行网络 fetch，不能据此断言远端服务器当前没有新提交。

开始时没有源码修改，只有三份历史未跟踪轨迹：RUN_1791610197.json、RUN_INVALID_1791610197_planner.json、RUN_VALID_1791610197_planner.json。记录了 61 个原有文件 SHA-256，安装修改前复核，最终除 README 和两个预定 HTTP 模块外原文件哈希保持一致。原有 Evidence、RC2、授权边界、ADR-001～004、CI 和全部原测试均未改动。暂存区保持为空。

## 2. 分阶段交付状态

| 阶段 | 已完成的工程工作 | 部分完成／尚未执行 |
| --- | --- | --- |
| C-2 | 纯请求适配器；独立、默认未启动的服务组件；非阻塞 socket Executor；单 I/O 所有者、最终授权 gate、首次正数发送计数、部分发送、关闭；实例／凭据绑定；最小响应证据与恢复检查 | socket 后端只有静态实现和 FakeSocket 测试；真实监听、实际派发、OS 调度／端口／取消延迟尚未验证 |
| C-3 | 业务核心→请求字节适配→内存传输→解析→判定→JSONL／Manifest／有限报告；Good 和三个独立缺陷配对；异常注入及独立证据核验 | [14 项真实集成](../eval/P3_http_integration_status.json) 全部 PENDING_AUTHORIZATION；未把模拟子场景当作完整 HTTP 验收 |
| REQ-021 | 固定顺序与基于有效拒绝证据补对照的确定性动态选择；36 次离线试跑；七项指标、计数、时间及限制；ADR-005 草案 | 尚无真实网络比较、完整人工成本数据与正式取舍批准，不预设动态更优 |
| CLI／交付 | simulate、compare、validate、verify、network-plan；模式隔离、固定错误码、复现说明、22 项追踪表 | 真实启动入口交由可信宿主在许可落实后集成；正式课程验收仍待人工 |

## 3. 实际修改与新增文件

修改：

- `README.md`：当前状态、离线入口和本轮审核链接；B／C-1 历史描述保留。
- `src/p3_core/http/machine.py`：共享 Controller 状态机的受控扩展点、选择策略、实际／模拟计数分离、证据关联、响应头事实、清理失败与有限报告。
- `src/p3_core/http/protocol.py`：有界响应头事实与经完整契约验证后的最小证据投影；原严格解析和判定规则保留。

新增：

- `src/p3_core/http/live.py`：可信绑定、受控非阻塞传输、实际运行子类；无任意 transport 注入。
- `src/p3_core/http/strategies.py`：固定和确定性动态选择。
- `src/p3_core/http/audit.py`：试跑容量限制、事件前缀／报告关联校验、只读恢复分析。
- `src/p3_core/mock_api/adapter.py`：严格 GET 字节到原业务核心的无网络桥接。
- `src/p3_core/mock_api/service.py`：许可门槛后才可启动的串行回环服务组件。
- `src/p3_core/experiments.py`：离线端到端驱动及同口径策略实验，合成登记明确 synthetic。
- `src/p3_core/delivery.py`：仅离线 CLI，不提供真实运行许可开关。
- `tests/test_remaining.py`：31 项新增测试，含多个 subTest。
- `design/ADR_005_deterministic_strategy_comparison.md`：Proposed，推荐保留固定，等待负责人审核。
- `docs/P3_offline_delivery.md`：复现方法、接口、许可流程和真实验收顺序。
- `eval/P3_offline_strategy_results.json`：36 次逐次离线结果。
- `eval/P3_http_integration_status.json`：真实集成待授权清单。
- `eval/P3_requirement_traceability.md`：22 项稳定需求—测试—证据追踪。
- 本报告。

共 17 个文件：3 个修改、14 个新增；不含原有未跟踪 Evidence。完整差异单独导出，包含全部新增文件，不依赖暂存操作。

## 4. 架构与安全审查要点

Planner／策略只能选已批准集合。Controller 逐项校验并生成当前 run 的一次性请求，Executor 不能选择目标、追加头或接受任意 URL。connect 与首次正字节 send 的最终复核、状态与计数共用短 gate；非阻塞网络调用不持有离线 Controller 的长锁，审计在 gate 外。撤权生效后不再发新字节；已发送字节无法撤回。重置实例须先撤销关联运行，待所有者清理后换实例；单独 invalidate 提示不是原子撤权替代品。

`request_count` 只由真实 socket 子类在首次正返回时增加；内存路径只增加 `model_request_count`。原 plan_count、attempt_count、重复 ID 防护、预算、NO_NEW_EVIDENCE 和不可重开终态保留。默认策略维持原登记处理顺序。

状态行／头部已识别但 body 不完整时，保留响应事实和错误来源；不能因此确认 PASS。异常、非法 JSON、重复长度、截断或超长响应不能凭 canary 确认 FAIL。正文持久化仅接受既有封闭 schema 与有限合成值；凭据及异常正文不进入日志。纯模拟结果保持 NOT_EXECUTED／INCONCLUSIVE，模拟断言独立列示。

网络与磁盘不是事务：发送后审计失败可能留下未知区间。恢复记录 unknown，不回收预算、不重放、不伪称未发送。Manifest 是完成标记；缺失／audit_gap 时证据不完整。哈希是本地完整性检查，不能代替真实批准、数字签名或抵抗有权重写整个目录的攻击者。

## 5. 测试命令、真实结果与失败记录

仓库根目录设置 `PYTHONPATH=src`、`PYTHONDONTWRITEBYTECODE=1` 后执行：

```text
C:\Users\20573\anaconda3\python.exe -m unittest discover -s tests -v
```

本机 Python 3.9.12，**158 项通过**，原 127 项全部保留，新增 31 项；没有跳过测试或删减安全断言。当前 CI 仍使用既有 Python 3.10 流程自动发现全部测试，但本轮未 Push，未声称运行新的 GitHub Actions。

首轮 148 项回归出现 1 failure、1 error：

1. `test_denials_consume_budget_and_eighth_ninth_boundary`：新选择器将尾部非法提案提前处理，改变原有调度顺序，计数断言 7≠8。修复选择器保持登记队首非法项处理及固定默认顺序；原测试不修改。
2. `test_faults_do_not_confirm_leaks` 的 audit 子场景：审计失败后请求已经清理，实验驱动仍读取 wire。修复为仅在 RUNNING 且存在活动请求时生成业务响应。

之后 148、154、157、158 项分别通过，后续补充完整性、头部事实与错凭据绑定测试。静态检查还修正了文档生成的 PowerShell 编码问题；最终文档为 UTF-8。最终完整日志独立交付。真实网络测试未执行，不写成 PASS 或 FAIL。

## 6. REQ-021 离线试跑结果

六类 × 两策略 × 三次 = 36 次独立运行。相同逻辑权限／候选／预算／目标，重置实例和凭据生成独立绑定；全部实际请求为 0。每个运行的事件／报告／Manifest 校验均 VERIFIED，仅表示本地完整性。

| 场景（每策略三次） | 固定：有效覆盖／目标 | 动态：有效覆盖／目标 | 每策略模型发送 | 每策略缺陷检出 |
| --- | --- | --- | --- | --- |
| Good | 18/18 | 18/18 | 18 | 不适用（分母 0） |
| AUTH | 18/18 | 18/18 | 18 | 3/3 |
| BOLA | 18/18 | 18/18 | 18 | 3/3 |
| RBAC | 18/18 | 18/18 | 18 | 3/3 |
| 非法 JSON | 0/18 | 0/18 | 3 | 不适用；各 18 项 INCONCLUSIVE |
| 超时 | 0/18 | 0/18 | 3 | 不适用；各 18 项 INCONCLUSIVE |

每策略共 78 次模型发送，误确认、观察到的未授权模型派发均为 0；真实未授权派发为 0（没有网络路径运行）。两类故障各三次运行安全停止，逐次保留工具故障和未覆盖清单。规划时间与本地总时间为真实 perf_counter 测量，详见 JSON；准备／人工复核时间 null，真实 HTTP 延迟与 Token 未测。样本不足以支持统计优势，当前未见动态请求节省，ADR-005 推荐保留固定默认。

## 7. 独立复核材料

交付目录位于本聊天工作区 `outputs/remaining-review/`，不混入历史 Evidence：

- `P3-remaining-development.diff`：全部本轮源码、文档及结果差异，含新增文件。
- `unittest-final.txt`：最终完整 unittest 日志。
- `comparison-full-final.json`：36 次完整报告及指标。
- `P3-offline-review-evidence-final.zip`：36 个 run 的 JSONL／Manifest／报告与比较原件。

离线证据包 SHA-256：`3c11ece7c44e931c11bc91976317771cad97a3567971f5abda903301f6f1bc3f`。包内明确 NO_NETWORK_SIMULATION；不是现实漏洞证据或批准材料。最终批次的规划时间包括首次计划和后续选择；此前初测输出原样保留，逐次结果文件只引用最终批次，不混合计算。

## 8. 残余风险与真正阻塞项

1. 未取得可核验目标所有者／受托人许可、教师目录记录、真实夹具监督记录。不能启动监听器或真实 Executor；材料真实性须人工审查，不能通过字段自称批准。
2. socket／服务组件没有真实 OS 集成验证。Windows／Linux connect_ex 差异、端口竞争、实际取消延迟、关闭失败及实际代理环境需要授权后验证。不会承诺线程或 socket 可立即撤回已发送请求。
3. 同进程模块不是安全沙箱；持有 Python 进程执行权限者能访问私有成员。可信宿主、注册表和撤权入口不能交给不可信 Planner。
4. 容量 64 KiB／1 MiB、服务处理 2 秒上限均为工程试跑配置，不是课程冻结。试跑边界和正式接受条件需负责人复核，班级最终预算按原治理要求办理。
5. 新证据保存经过验证的有限合成字段，不保留任意真实 HTTP 原文；不宣称通用 HTTP 脱敏完成。真实响应证据充分性与人工复核仍待授权试跑。
6. REQ-021 离线比较已完成，真实成本、完整人工时间、正式工程取舍和课程验收尚未完成；ADR-005 保持 Proposed。REQ-022 真实 LLM 未接入。

这些事项阻塞真实网络与正式验收，不否定本轮离线测试，也不扩大为普通工程技术选择的教师前置审批。

## 9. 建议分批 Commit（由负责人审核后操作）

1. `feat: add gated HTTP components and offline integration harness`：两个修改的 HTTP 模块、live／audit／strategies、adapter／service、experiments／delivery 和新增 tests。代码与测试作为同一批，避免中间提交无法运行。
2. `docs: document offline delivery and pending HTTP acceptance`：README、交付说明、追踪表、C-3 状态、逐次策略结果、ADR-005 和本报告。

不要把三份历史未跟踪轨迹自动加入本轮提交。完整 diff 与 zip 供外部审核，是否纳入版本库另行决定。本轮在人工审核阶段停止。
