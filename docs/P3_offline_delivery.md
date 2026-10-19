# P3 离线交付与真实接入准备

## 可复现入口

Python 3.9+，仅标准库，在仓库根目录 PowerShell：

```powershell
$env:PYTHONPATH = 'src'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m unittest discover -s tests -v
python -m p3_core.delivery simulate --mode good --strategy fixed --output "$env:TEMP/p3-review-runs"
python -m p3_core.delivery simulate --mode bola --strategy dynamic --output "$env:TEMP/p3-review-runs"
python -m p3_core.delivery compare --repeats 3 --output "$env:TEMP/p3-comparison-runs"
python -m p3_core.delivery network-plan
python -m p3_core.delivery verify <run目录>
python -m p3_core.delivery validate <http-local配置文件>
```

Linux 可设置 `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1` 后执行相同 Python 命令。旧 `python -m p3_core --config examples/offline.json --output ...` 保持原语义，不将 offline 配置当成 http-local 许可。

新入口退出码：0 表示命令完成；1 表示单次模拟安全停止或证据校验不完整；2 表示输入／输出错误。比较命令包含预期故障样本，因此完成比较返回 0，并逐行保留 STOPPED。任何退出码均不表示正式安全验收。输出为 JSON；每次 Evidence 使用唯一目录、独占创建，不能覆盖旧 run。

模式 good/auth/bola/rbac；策略 fixed/dynamic。故障选项 malformed、truncated、redirect、timeout、transport、audit、empty、server_error、duplicate_length 均为内存注入。所有普通 CLI 均没有启动网络的选项。`validate` 只验证配置 schema，不验证人工批准材料，更不授予派发权。

## 证据与成本口径

`report.json` 把 authorization、execution、conclusion 分开。模拟运行 execution=NOT_EXECUTED、conclusion=INCONCLUSIVE；业务判定只放在 simulated_conclusion。模型首次正字节发送计 model_request_count，request_count=0。

events.jsonl 仅保存受控事件、检查关联、已验证封闭 schema 的合成响应字段；错误响应不保存原始正文、任意头或异常文本。Manifest 关联事件前缀哈希和报告规范化哈希。`verify` 验证关联与完整性，不提供防恶意篡改签名，不证明批准真实性。历史格式没有新报告哈希时返回不完整，不修改它们。

1 MiB 运行容量及响应 64 KiB 为本轮可配置实验值，不是教师冻结值。容量不足按 AUDIT_ERROR 停止；Manifest 缺失或 audit_gap=true 的运行不能用于确认结论。恢复只分析前缀；有 prepared、无发送后审计时标记 unknown，不推断未发送，不重放。终态后追加记录不在已完成 Manifest 前缀内，校验结果单列 appended_bytes。

## C-2 接口和信任边界

- `ServiceAdapter.handle_bytes` 是无网络的严格 HTTP 请求到业务核心桥梁；`AuthorizedService` 是独立、默认未启动的串行监听组件。仅明确调用 start 且真实登记核验通过才可能监听回环地址。
- `AuthorizedHttpRun` 复用独立 Controller 状态机，内部生成一次性 PreparedRequest 与私有 socket 传输。不得从 Planner 注入 transport 或任意 URL。标准库非阻塞 socket 直连字面回环地址，无代理、重定向或自动重试层。
- 可信宿主先核验目标所有者／受托人材料与教师目录来源、内容哈希、精确版本范围、生效和失效时间；由 `LocalRegistry` 得到只读快照。仅填写姓名或 active 字段不能通过 schema／登记核验。材料真实性仍依赖人工来源审查，不声称密码学认证。
- 夹具管理器新建实例后，宿主构造 `FixtureBinding`：实例、范围摘要、管理记录引用、生成凭据集合摘要和 `InstanceStatus`。执行器与服务均核对实例和凭据绑定，避免把错凭据导致的拒绝当成权限缺陷。摘要不输出凭据；该对象由可信宿主掌握，不能作为不可信输入自签许可。
- 最终 connect／send 在短 gate 内复核授权、撤权、generation、剩余预算和实例有效性。首次 send 返回正数与计数在同一 gate 内提交，部分发送只计一次；持久化在 gate 外，撤权不等待磁盘或阻塞网络调用。实际返回 BlockingIOError 可等待就绪，不发起新请求或重连。
- 单 I/O 所有者负责读写和关闭。已发送字节不可撤回；撤权停止之后的新写入，后续清理关闭连接。迟到响应不能升级终态。收到可识别完整头部但正文缺失仍保留 HTTP 事实；结论 INCONCLUSIVE。
- 监督者重置实例时须先对关联运行调用 `revoke()`，再 invalidate 旧绑定，等待 I/O 所有者关闭后才能替换服务。单独切换 InstanceStatus 是失效提示，不替代与 send 共用 gate 的撤权线性化入口。
- 服务适配器不处理登录、重置或模式切换接口；读写受本次处理总截止约束，不能通过逐字节慢输入无限延长。服务不是任意同进程恶意代码的沙箱。

## C-3 尚待授权的步骤

实际网络全部见 [状态清单](../eval/P3_http_integration_status.json)，为 PENDING_AUTHORIZATION。未取得可核验目标许可、教师目录材料及真实夹具监督记录；预算最终冻结、课程正式验收和策略正式取舍仍按治理分类处理，不扩大为普通开发前置审批。

许可落实后先审查材料和范围；由可信宿主创建服务与 Executor（本轮没有可直接启动它们的 CLI）；先跑 Good 配对，再分别重置 AUTH/BOLA/RBAC；随后覆盖异常、撤权竞态、审计故障和资源释放。必须测量操作系统实际 connect/send、取消延迟、端口占用与身份绑定，验证代理环境、重定向和地址变化没有旁路。普通 push 的 CI 继续只运行无网络测试。

真实响应采集、系统调度竞态、真实取消延迟、完整 HTTP GWT、实际策略成本及正式人工验收均未执行。本轮模拟包不能替代这些材料。
