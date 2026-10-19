# P3 第三阶段第二轮 C-1：模拟 API 纯业务核心审核报告

日期：2026-10-19。状态：C-1 代码及无网络验证完成，等待人工代码审核；C-2 未开始。所有结果为模拟，不是实际 HTTP 集成或真实漏洞报告。

## 1. 基线与范围

实际 Git 仓库为 `D:/project/-P3-Security-Testing-Agent`；`D:/project-P3-Security-Testing-Agent` 是此前差异导出目录，未发现该目录是当前 Git 工作区。本轮以实际仓库 HEAD `bd888e2` 开始；本地缓存 origin/main 同步，暂存区为空，三份原未跟踪 Evidence 保留。用户提供的 Actions #9 成功作为阶段背景，本轮未联网复核 Actions、未 fetch、未产生被测 HTTP 请求。

已核对 RC2、授权边界、HTTP 契约／设计、ADR-003／004、验收计划、全部 http 模块及其测试、上一轮报告和 CI。沿用 Accepted 技术路线；本轮只补服务端纯业务逻辑，不改 Controller、解析器、判定器、RC2、CI 或既有 Evidence。

## 2. 新增／修改文件

| 文件 | 变更 |
| --- | --- |
| [mock_api/__init__.py](../src/p3_core/mock_api/__init__.py) | 新增纯业务模块导出，未提供网络入口 |
| [mock_api/core.py](../src/p3_core/mock_api/core.py) | 新增 FixtureManager、不可变 Fixture、四种互斥 Mode、MockRequest／MockResponse 和固定错误码 |
| [test_mock_api.py](../tests/test_mock_api.py) | 新增 24 项 unittest，纯业务矩阵、模式隔离、重置、泄漏防护和 HTTP 模型兼容性 |
| [README](../README.md) | 补充 C-1 当前状态、命令及限制 |
| 本报告 | 测试事实、接口、C-2 待办与授权门槛 |

未修改 tests/test_core.py 或 tests/test_http_core.py；继续使用其中的测试专用许可构造辅助函数，它们不成为业务核心依赖，也不是真实批准材料。

## 3. 业务行为与接口

可信本地夹具管理器调用 `FixtureManager.reset(Mode.GOOD/AUTH/BOLA/RBAC)`，每次返回独立不可变实例。实例 ID 在其生命周期内固定；凭据为 `mock_` 前缀的合成值，包含新实例标识、模拟用户标识和随机部分。所有用户／角色／对象归属固定，只有选定的一项权限缺陷开关改变。没有从环境变量、文件或外部系统导入账号／Token 的入口。

`fixture.credential_for(identity_ref)` 与 `credential_bindings()` 仅供可信测试宿主在内存绑定身份／凭据；anonymous 返回 None。取出的映射为副本，不可借修改映射改变夹具权限。Fixture、请求及身份对象的 repr 隐藏凭据／原始目标；模块不输出日志、不写文件。

`fixture.handle(MockRequest(method, target, action_id, credential)) -> MockResponse` 只处理结构化请求；根据当前实例凭据识别身份，不接受身份、角色、expected、模式或额外请求头覆盖。原始 Token 以独立内存字段传递，不放进业务 JSON。`MockResponse.to_bytes()` 只序列化 HTTP/1.1 状态行、Content-Type、按 UTF-8 字节数计算的唯一 Content-Length、Connection: close 与封闭 JSON；不执行任何 I/O。

路径精确限定 `/v1/profile`、两个既有对象实例 `/v1/objects/obj-a` 和 `/v1/objects/obj-b`、`/v1/admin/report?period=demo`。编码、附加／重复查询、其他对象、方法或管理路径抛出固定 `RequestRejected`，不插值原始请求。该内部拒绝不是新定义的 400／404 响应；未来服务适配器需单独确定传输层拒绝策略，不改写三类检查的 401／403 契约。

业务矩阵包含 obj-a 和全部身份组合，但 Agent 候选仍严格为已登记六项。纯单元测试核对矩阵不等于批准 Agent 派发矩阵全部单元格。

| 模式 | 六项按既有顺序的状态码 | 模拟独立判定 |
| --- | --- | --- |
| Good | 200、401、200、403、200、403 | 六项 PASS |
| Known Bad / AUTH | 200、200、200、403、200、403 | 仅 HTTP-N-AUTH FAIL |
| Known Bad / BOLA | 200、401、200、200、200、403 | 仅 HTTP-N-BOLA FAIL |
| Known Bad / RBAC | 200、401、200、403、200、200 | 仅 HTTP-N-RBAC FAIL |

AUTH 缺陷明确限定“不提供凭据的 profile 请求”返回 alice 合成资料；显式错误或旧实例凭据仍拒绝，不把旧凭据误当有效用户。BOLA 仍要求认证，RBAC 仍要求认证并保持对象所有者检查。各模式三个合法对照均成功；Good 中 admin 没有隐含跨对象特权。

业务核心不导入 Agent 权限矩阵函数或 evaluate，不返回模式、漏洞名称、预期值、PASS／FAIL；这些只在测试夹具真值与独立判定器中比较。JSON 仅包含当前 fixture_instance_id、contract_version、等于 action_id 的 request_id，以及契约 data 或 error 字段。

## 4. 实际测试结果

仓库根目录 PowerShell：

```powershell
$env:PYTHONPATH = 'src'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m unittest discover -s tests -v
```

本机 Python 3.9.12 实际运行：**127 tests，1.093s，OK**；原有 103 项通过，新增 24 项通过。耗时仅为本次运行记录，不作为性能达标依据。新增测试在 setUp 禁止 socket、create_connection、getaddrinfo；没有服务、端口监听或网络连接。

新增测试覆盖：

- 四模式六项候选及各自合法对照；独立核对四身份 × 四路径实例 × 四模式的业务权限矩阵。
- 未注册身份、无效凭据、方法、对象、路径编码、额外／重复参数、管理入口和非法 action_id 的固定拒绝。
- 不可变模式、独立新实例、旧凭据失效于新实例、身份映射副本不影响原夹具；保留旧对象不意味着有运行中的 HTTP 服务。
- 闭合 JSON、字节长度、request_id／版本／实例关联，不带预期判定；重复同一结构化输入得到相同响应。
- 凭据、恶意参数不出现在 stdout/stderr、捕获日志、对象 repr、响应或固定异常文案；全链路临时 JSONL／Manifest／Report 扫描无原始凭据。
- 业务响应经现有 build_request、ResponseParser、evaluate 兼容验证，并通过 SimulationRun＋MemoryTransport 完成六项模型闭环。

每个模型运行 `plan_count=6`、`attempt_count=6`、`model_request_count=6`、真实 `request_count=0`；输出仍是 `execution=NOT_EXECUTED`、实际 API `conclusion=INCONCLUSIVE`，模拟判定单列 `simulated_conclusion`。未产生真实漏洞 Finding。

## 5. C-2 接口与待办（本轮未实现）

1. **可信启动和服务适配器**：先取得许可，可信监督进程生成 Fixture，登记实例 ID、契约／数据版本与精确回环 scheme/host/port。适配器只绑定获准地址；限制请求头／请求体大小，严格提取 GET request-target、Controller 生成的 X-P3-Action-Id 和可选 Bearer，构造 MockRequest，调用 handle 后写出 to_bytes。不得接受客户端声明身份、角色、expected 或 mode；不得增加登录、重置或模式 HTTP 路由。严格路径不解码后再放宽，重复敏感头应拒绝，传输层错误处理须审核。
2. **实例重置**：可信监督者先撤销旧 run、停止旧服务并确认在途资源结束，再切换到新 Fixture，重新核验新实例绑定及许可。reset 返回新对象但不自动撤销其他 run；仍持有旧 Python 对象的调用者属于可信测试宿主，不代表热切换获准。模式变化同样走新实例，不在运行内修改。
3. **真实 Executor**：新增独立真实传输路径，保留当前 SimulationRun／MemoryTransport 的模拟来源。只消费 Controller 批准的一次性执行对象，关联 snapshot、generation、action 和参数规范字节；单 I/O 所有者推进非阻塞 connect/write/read，不能把阻塞 HTTP 放回原 offline Controller 的锁内。尚需审核真实调度器、异常分类、资源关闭、代理禁用、不重定向和不重试。
4. **计数与最终复核**：真实 request_count 只在真实 send 首次返回正字节时加 1，部分续写不重复；model_request_count 不迁移成真实计数。connect 不计 HTTP 请求但仍是受授权约束的网络动作。connect 与每次 send 的同一短 gate 内复核运行状态、范围／版本、generation、有效期、审计健康、单调截止、唯一动作与偏移；撤权置位先于 gate 操作时不调用 connect/send。保留 RC2 登记与尝试预算。
5. **撤权验收**：沿用 HTTP-T27～T31 确定性屏障模型，再在已获准本地集成中测试 connect 前、连接后首写前、首写正字节返回与记账间、部分续写前及读取等待中的撤权。记录收到／生效顺序、首次发送事实、取消申请与资源回收延迟。Python 线程不能强杀网络请求，已入内核字节不可撤回；不得用模型通过替代 OS 行为实测。
6. **真实证据**：保存实际请求规范摘要、授权／动作／实例绑定、真实派发时间与字节事实、响应状态及完整性、经过 allowlist 校验且可复核的合成 JSON 字段／断言、合法对照关联及 Manifest 哈希；不得保存 Token、未知字段、异常原文或未批准参数。真实响应缺失／截断不能 PASS，偶然 canary 不能救回损坏响应。先审计准备、再派发，派发后审计失败标缺口、停止新动作、不自动重试；容量／保留片段和停止元数据预留仍需实验确认。
7. **真实授权阻塞**：现有仓库尚无本次实际目标所有者／正式受托者许可、委托证明（如适用）、教师批准 target/test_id 目录及核验登记。需覆盖确切回环端口、六项检查及对照、身份、参数、有效期、预算和撤权责任；active=true、测试合成材料或技术方案 Accepted 不能替代。8／90／1 仍属试跑值，班级预算冻结与正式课程验收阶段规则保持不变。

REQ-021 固定／动态比较仍 MUST、尚未完成；不因本轮夹具可运行于内存而开始策略实验或宣称项目完整验收。

## 6. 风险、差异及人工审核

Fixture 是同进程可信宿主对象，不是 OS 沙箱；其构造与凭据读取接口只能由可信管理器／测试使用，不能暴露给 Planner 或 HTTP 客户端。Python 对象私有字段和 frozen 数据类不防任意同进程恶意代码。没有主动原始日志，但宿主自行打印 credential_bindings 或捕获包含 locals 的异常仍可能泄露，C-2 适配器必须禁用此类访问日志。

唯一 action_id 由 Controller 生成并绑定；业务核心验证既有 action_UUID 形状并回显对应 request_id，不建立服务端防重放账本，不重写客户端动作 ID。每检查最多一次请求仍由 Controller／Executor 保证。核心正常响应没有 5xx 注入功能；故障注入设计需单独获准，不能与四种业务缺陷混淆。

本轮没有架构改线，沿用 ADR-003／004，不为普通业务细节新增重复 ADR。只新增两个模块文件、一个测试文件和本报告，更新 README；最终完整差异包含未跟踪的新文件，另导出到聊天工作区供审核，不修改暂存区。本轮不 Commit、不 Push、不进入 C-2。
