# P3 本地 HTTP 契约草案

修订：2026-10-19，仅澄清竞争边界、授权登记和异常响应；未实现或执行新测试。

日期：2026-10-14。状态：**Draft／待项目负责人审核；未实现、未执行 HTTP 测试、不构成目标授权**。

基线：[RC2](P3_specification_v1.0-rc2.md)、[授权边界](P3_authorization_boundary.md)、[治理登记](P3_decision_governance.md)。配套：[接入设计](../design/P3_http_integration_design.md)、[验收计划](../eval/P3_http_acceptance_plan.md)。本文件中的新字段、端点和检查 ID 都是设计候选，不替换稳定需求／GWT 编号。

## 1. 目标、模式和准备边界

仅设计 `scheme=http`、`host=127.0.0.1`、`port=8765` 的隔离模拟服务；8765 是待核定示例端口，不是已批准目的地。执行配置必须登记唯一确切端口，禁止占用失败后自动递增端口、改用 localhost、其他 127/8 地址、IPv6、通配监听或公网。端口改变必须重新登记并创建运行。首版限 IPv4，IPv6 支持另作工程评审。

未来服务只绑定登记的回环 IP；可信夹具管理器用本地进程配置选择模式并准备数据。没有 HTTP 重置、登录、切换模式或管理端点，Planner 不能改变夹具。重置通过本地生命周期完成，不能在一轮运行中切换模式／归属／Token。启动、重置和集成测试均留待下一轮明确授权。

| 模式 | 用途 | 能否据此发 HTTP |
| --- | --- | --- |
| 现有 `mode=offline` | 当前 49 项测试和假派发；`examples/offline.json` 原样保留 | 不能；绝不自动升级或沿用示例批准者作为许可 |
| 拟议 `mode=http-local`、`schema_version=http-auth-draft-1` | 实际本地请求的独立可信登记 | 只有本文件全部执行门槛满足后；当前代码不支持此模式 |

静态预检只读取本地登记、许可和夹具就绪材料，不能用 HTTP health check 验证目标。额外健康请求若将来需要，必须显式登记为独立检查并计数。准备夹具不计运行预算；静态预检后、第一次规划前设置唯一 t0，之后连接、收发、判定、审计全部计时。

## 2. 模拟身份和对象

| identity_ref | 模拟主体／角色 | credential_ref | 说明 |
| --- | --- | --- | --- |
| anonymous | 无主体／anonymous | null | 不发送 Authorization，不回退到其他身份 |
| user_alice | alice／member | fixture/alice | 每次重置由可信管理器生成，仅在内存解析 |
| user_bob | bob／member | fixture/bob | 与 alice 的凭据不同 |
| admin_carol | carol／admin | fixture/carol | 仅供批准的高权限对照 |

原始模拟 Bearer 值不进入计划、注册表可展示部分、日志或报告，不允许从任意环境变量或宿主凭据目录解析。凭据引用绑定当前 `fixture_instance_id` 与角色映射；缺失、重用旧实例或映射矛盾即失败关闭。这里只有引用，没有真实账号或可用 Token。

对象集合：`obj-a` 归 alice，`obj-b` 归 bob；受保护数据分别为合成标记 `OBJECT_A_CANARY`、`OBJECT_B_CANARY`。管理员报表标记为 `ADMIN_REPORT_CANARY`。这些标记是可公开的模拟断言值，不是密码；真实凭据绝不作为断言值保存。权限矩阵独立于服务的 Good／Known Bad 开关，切换缺陷模式不得切换期望答案。

## 3. 端点和请求的精确定义

全部 GET、无请求体、无 Cookie、无自动重试。允许请求头由 Controller 构造：精确 Host、`Accept: application/json`、`Connection: close`、固定版本 User-Agent、需要时的 Authorization，以及生成的 `X-P3-Action-Id`。Planner 不提供请求头。

| endpoint_id | 路径模板 | 路径参数 | 查询参数 | 保护对象 |
| --- | --- | --- | --- | --- |
| profile_read | `/v1/profile` | 无 | 无 | 已认证用户的个人模拟资料 |
| object_read | `/v1/objects/{object_id}` | `object_id` 精确为 obj-a 或 obj-b | 无 | 指定对象及受保护标记；只有所有者可读，admin 不隐含跨对象特权 |
| admin_report | `/v1/admin/report` | 无 | 必须且仅有 `period=demo` | 仅 admin 可读的模拟报表 |

路径参数／查询参数分开建模，不把一个扁平 params 字典同时解释成两种来源。无通配值、重复 query key、空值或额外参数。以注册表中的有限字符串构造规范 request-target；对象值和 period 均不含需要编码的字符，因此首版拒绝输入中的 `%`、点段、反斜线、控制字符、绝对 URL、fragment、`//` 和 Unicode 路径变体，不尝试宽松“修正”。将来扩大参数字母表须先修订契约并评审编码算法。

## 4. 预期业务权限矩阵与批准检查

以下矩阵说明 API 应如何工作，**不是 Agent 的测试授权**。明确矩阵中的一个单元格不表示该组合自动加入可执行候选。

| 身份 | profile_read | object_read / obj-a | object_read / obj-b | admin_report / period=demo |
| --- | --- | --- | --- | --- |
| anonymous | DENY / 401 | DENY / 401 | DENY / 401 | DENY / 401 |
| user_alice | ALLOW / 200 | ALLOW / 200 | DENY / 403 | DENY / 403 |
| user_bob | ALLOW / 200 | DENY / 403 | ALLOW / 200 | DENY / 403 |
| admin_carol | ALLOW / 200 | DENY / 403 | DENY / 403 | ALLOW / 200 |

建议首轮固定批准集合恰好六项，每项独立占名额；采用对照在前的顺序，六项不是课程硬编码要求：

| check_id（新候选名） | kind | endpoint / 参数 | identity | expected | control_id |
| --- | --- | --- | --- | --- | --- |
| HTTP-C-AUTH | control | profile_read / 无 | user_alice | ALLOW | null |
| HTTP-N-AUTH | anonymous | profile_read / 无 | anonymous | DENY | HTTP-C-AUTH |
| HTTP-C-BOLA | control | object_read / obj-b | user_bob | ALLOW | null |
| HTTP-N-BOLA | object | object_read / obj-b | user_alice | DENY | HTTP-C-BOLA |
| HTTP-C-RBAC | control | admin_report / period=demo | admin_carol | ALLOW | null |
| HTTP-N-RBAC | role | admin_report / period=demo | user_alice | DENY | HTTP-C-RBAC |

六项须分别出现在教师批准测试目录与目标授权范围内，不能靠矩阵的 ALLOW/DENY 自动生成许可。对照关联同一 fixture instance、端点、对象／查询和契约版本，仅身份按批准组合不同。缺对照的负向拒绝只可 INCONCLUSIVE。obj-a 和矩阵其他单元格留作可扩展夹具，不在这六项候选内；需要执行时另行批准，不临时发现或探测。

## 5. JSON 契约与可确认的响应事实

通用响应：`Content-Type: application/json`、明确且唯一的 Content-Length、UTF-8 JSON object；不压缩、不分块传输、不重定向。每个正常响应包含精确 `fixture_instance_id`、`contract_version`、`request_id`（等于当前生成 action_id）。本地可信管理器的启动记录提供预期 fixture instance、模式和代码／数据版本；响应自报实例号不能单独证明目标可信。

| 响应类型 | 必要 JSON 断言 |
| --- | --- |
| profile 200 | `data.user_id` 对应可信身份映射；`data.role` 正确；`data.profile_marker` 为该用户已登记的合成标记。alice 对照为 ALICE_PROFILE_CANARY |
| object 200 | `data.object_id` 精确等于请求对象；`data.owner_id` 与夹具所有权一致；`data.protected_marker` 等于该对象的合成标记 |
| admin report 200 | `data.period=demo`、`data.audience=admin`、`data.report_marker=ADMIN_REPORT_CANARY` |
| 401 | `error.code=AUTHENTICATION_REQUIRED`；不得存在 data 或任何受保护标记；只允许固定错误字段，不回显 Token／用户输入 |
| 403 | `error.code=ACCESS_DENIED`；不得存在 data 或任何受保护标记；同上 |

成功和拒绝采用封闭 JSON schema：除通用关联字段及表内对应字段外不接受额外字段、重复 JSON key、NaN 或错误类型。拒绝的“不泄露”必须基于完整、符合 schema 的响应，不能因只读取前缀没看到标记就 PASS。响应 404 不是本基线三个负向检查的预期拒绝：已知对象应存在，404 暂为 INCONCLUSIVE，检查对照与夹具；后续若业务采用 404 隐藏策略，先批准新的契约再改变判定。

能确认泄露需要：获准负向请求的身份／规范请求可确认，响应来源与本次动作可关联，存在结构明确的受保护标记及对应对象／角色字段。标记在任意异常文本中出现不自动证明泄露。对照成功支持正确拒绝判定；独立充分泄露证据存在时，不因缺对照掩盖 FAIL。完整判定见接入设计 §6。

## 6. Good / Known Bad 与重置

| 夹具配置 | 行为差异 | 预期可观察结果（待测） |
| --- | --- | --- |
| Good | 按上表认证、对象所有者和 admin 角色校验 | 六项均有充分证据时 PASS |
| Known Bad / AUTH | 仅 profile_read 漏掉认证校验，anonymous 返回 alice 的完整资料和合成标记 | HTTP-N-AUTH 可确认 FAIL；其他两类仍 Good |
| Known Bad / BOLA | object_read 仍认证，但漏掉所有者比较 | alice 读 obj-b 得到 bob 对象完整内容，HTTP-N-BOLA FAIL |
| Known Bad / RBAC | admin_report 仍认证，但漏掉 admin 角色比较 | alice 得到完整管理员报表，HTTP-N-RBAC FAIL |

每轮只选择一种缺陷变体，以免混淆根因；也不把全部 Known Bad 混作一次固定真值。合法对照在三个 Known Bad 变体都应正常工作。服务不能返回“测试已通过”的自评字段；Agent 依据契约独立判断。夹具真值清单只用于验收计算正确检出，不代替响应证据。

重置步骤设计为：可信操作者停止旧实例、确认旧请求结束、清空仅属于新模拟实例的内存数据、重建对象和凭据、生成新实例 ID／启动记录，再创建新 Agent run。不能删除历史 Evidence，也不能在停止后偷偷复用同一 run。超时／5xx／错误 JSON／截断等是独立故障注入配置，不伪装成三类授权缺陷。

## 7. 实际授权登记契约（字段规范，不是可运行配置）

| 字段组 | 最低字段与核验 |
| --- | --- |
| 类型与标识 | mode=http-local、schema_version、authorization_id、authorization_version、contract_version、matrix_version、candidate_set_version；所有版本与登记快照绑定 |
| 目标许可 | owner_or_delegate_id、authority_basis、delegation_record_ref（受托时必需）、target_permission_record_ref、permission_digest、approved_scope_digest、approved_at、valid_from、valid_until |
| 教师目录 | teacher_catalog_record_ref、catalog_version、catalog_digest、批准的 target_id／test_id 映射；引用应可由可信核验者读取，不能只是一段名称 |
| 可信核验记录 | verified_by、verified_at、verification_record_ref；核验者依据本地已批准签署／批准记录核对身份、委托链、范围、时间及撤销状态。哈希只能确认版本一致，不能证明批准人真实性 |
| 精确目标 | target_id、scheme=http、host=127.0.0.1、port=明确整数；fixture code/data version、fixture_instance_id、管理器启动记录与目标绑定 |
| 请求范围 | endpoint_id、method=GET、path template、规范路径实例、路径／查询参数完整组合、只读声明、允许的固定头字段；不接受 origin/path 的 Planner 覆盖 |
| 身份／候选 | identity_ref→credential_ref→模拟主体／角色；精确 check_id、expected、control_id；获准六项或独立批准的其他有限集合 |
| 预算 | max_checks、logical_timeout_seconds、concurrency=1、budget_version、budget_status=trial 或有依据的 class_frozen、budget_record_ref；8／90／1 仍为试跑示例 |
| 停止 | revocation_channel_ref、撤权操作者权限、authorization_generation、撤销状态与发生时间；运行中只减权，不允许重载扩权 |
| 审计／存储 | evidence_root、redaction_profile_version、拟采用容量配置及实验卡引用、许可材料的可公开摘要引用；材料正文和原始凭据不复制进运行日志 |

`active=true` 只是运行开关，批准者姓名只是定位信息。启动条件是：批准材料真实可核验且未撤销、可信核验记录绑定同一范围摘要、教师目录与目标许可均覆盖本次动作、当前有效期及夹具绑定正确。缺失、占位字符串、引用无法读取、摘要不一致、权属不明、过期或撤销，一律停止；不得网络查询来“补授权”。本轮所有真实许可字段均尚未取得可执行记录，不能由 Agent 填入“已批准”。

初始静态预检失败沿 RC2 使用 STOPPED/INVALID_INPUT，附稳定细分原因，例如 MISSING_TARGET_PERMISSION／MISSING_CATALOG_APPROVAL／UNVERIFIED_APPROVAL；不调用 Planner、不创建连接，计数均为 0。运行中许可失效为 AUTHORIZATION_INVALID，可信撤权为 REVOKED，优先级不变。有效期由可信时间源核验，并映射成不会因墙钟回拨延长的单调截止；不重置运行 t0。任何配置修改要求新的批准核验和新 run。

治理分工：端点／状态机／身份模型／证据格式由负责人 B 类审核；具体目标许可由所有者或正式受托者提供；教师目录 A-01 在网络执行前满足；班级预算 A-02 在正式冻结阶段满足；正式契约／评分 A-03～06 按既有阶段处理。不得新增“每个技术细节等教师审批”的门槛。

### 7.1 最小可实现的本地授权登记流程

1. **取得材料**：由目标所有者或正式受托负责人提供明确许可，由教师提供目录批准记录。可使用实际签署文件、课程平台导出记录或能核对发件人与批准内容的消息导出；保留原来源、日期、批准范围及委托依据。Planner 生成的批准文本、草案模板和自填姓名不算材料。本轮不取得新批准、不联网验证。
2. **指定核验者**：负责人指定可信本地操作者核对来源、批准人身份／权属、委托链、有效期与撤销状态，记录 verified_by、核验日期、材料路径／摘要及逐项核验结果。负责人具有相应身份时可以兼任，不强制另设机构；软件能核对记录一致性，不能仅凭字符串自动证明真实授权。
3. **计算获准交集**：逐项核对目标许可与教师目录共同覆盖的 scheme/host/port、endpoint/method、完整参数组合、身份、六项检查及必要对照、只读动作、时间和预算。登记必须是共同许可的子集；缺项或矛盾失败关闭，不把矩阵的业务 ALLOW 当测试许可。不能用笛卡尔积扩展身份／参数组合。
4. **生成版本快照**：可信操作者将核验结果与实际材料引用写入本地登记；发布 authorization_id/version、snapshot_id、范围摘要及契约／矩阵／候选／预算／夹具版本绑定。宿主目录访问控制只允许可信操作者写入，运行路径以只读方式加载；核验同一份读取到的字节并解析成不可变内存快照，Controller 与 Executor 共用它，不先验哈希再重读可变文件。摘要用于检测内容变化，不冒充签名；本轮不引入 PKI 或复杂签名服务。
5. **静态预检与使用**：缺真实材料、核验记录、版本绑定或授权交集时 INVALID_INPUT、零网络。运行执行对象绑定 snapshot_id、版本、generation 与 action；最终 gate 用该快照及当前撤权／有效期状态复核。运行中磁盘登记被修改不自动加载或扩权；可信操作者修改许可前先撤销旧 run，再发布新版本并重新核验。普通文件变化不能替代即时撤权通知。
6. **可信撤权**：操作者通过受宿主权限保护的本地入口指定 authorization_id/version/run，门内置位并增加 generation；记录操作者引用、原因码、收到／生效时间及事件序号。目标所有者或教师撤销许可须由可信操作者及时转入此入口；本地系统不假称自动获知外部撤销。重复撤权幂等，旧快照不得再派发，恢复或扩权必须新核验、新版本、新 run。

许可来源文件与原始凭据不得复制进运行 Evidence，仅存可公开引用与摘要。该流程依赖可信宿主和操作者诚实核验，不能抵御有权篡改宿主的攻击者；不新增教师技术选型审批门槛。

### 7.2 响应完整性约束的统一解释

适用接入设计 §6.1：重复／冲突长度、非法 JSON、超长或截断响应均先判证据有效性，本次必要证据不完整则 INCONCLUSIVE，禁止扫描偶然 canary 后直接 FAIL。5xx 只有在 framing、完整 JSON、来源关联、泄露断言与持久化均有效时才可确认 FAIL，并同时 RESPONSE_ERROR；其他完整检查的既有结论与本次损坏检查分别报告。因断连／超时／审计失败导致的缺口分别按既有 TRANSPORT_ERROR／TIMEOUT（总预算优先）／AUDIT_ERROR 处理，不改变 RC2 停止优先级。

## 8. 第二轮 B 无网络 schema 与接口（2026-10-19）

`HttpConfig.parse` 接受独立 `mode=http-local`、`schema_version=http-core-v1`；这是从草案字段落实的版本名，不沿用 offline 授权。顶层字段严格为 mode、schema_version、target、budget、limits、authorization、fixture_instance_id、contract_version、matrix_version、candidate_version、fixture_version、budget_version、candidates。未知／缺失字段拒绝。

- target 为精确 scheme=http、host=127.0.0.1、port；budget 为 max_checks、logical_timeout_seconds、concurrency=1。
- limits 为 header_bytes、body_bytes、response_bytes，均为正整数且总容量至少容纳前两者；测试中的 1024／4096／5120 只是单元测试边界，非课程冻结或正式性能参数。
- authorization 只含 authorization_id、authorization_version、registry_ref；不接受 active 或 approved_by 作为字段捷径。
- contract_version=p3-http-v1、matrix_version=p3-matrix-v1 绑定本文有限端点／身份／矩阵；candidates 必须精确为六项原始候选，使用分离 path_params/query。扩展候选／契约需新版本和评审，不能由 Planner 扩展。

可信宿主另提供 `LocalRegistry(registration_bytes, reviewed_materials)`。登记字节严格含 registry_ref、authorization_id、authorization_version、scope_digest、owner_ref、catalog_ref、delegation_ref。材料对象包含原字节及摘要、来源、核验者、授权主体／角色、共同范围摘要、有效期、撤销状态与 synthetic 标记；受托许可还核验委托记录。版本、目标、参数、身份、预算与夹具均纳入范围摘要。

默认 snapshot 不接受 synthetic 材料；只在显式 simulation=True 时允许人工测试替身，仍不得用于真实网络。`SimulationRun` 仅能调用内存传输，所有测试许可明确是人工构造材料。程序核验字节／范围／版本的一致性，真实性和宿主目录写权限是调用者信任边界，不宣称自动识别伪造批准。

凭据通过可信宿主独立内存映射传入 fixture/alice、fixture/bob、fixture/carol；不能由检查提案传头字段或原始 Token。示例和材料替身仅位于 tests/test_http_core.py，不提供可冒充真实许可的运行配置。批准材料全文、原始响应、未知参数和异常正文不进入 Evidence。
