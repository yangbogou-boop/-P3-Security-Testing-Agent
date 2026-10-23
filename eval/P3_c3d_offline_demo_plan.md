# C-3D 离线演示与验收计划

以下命令只使用内存传输，不启动服务、不创建 socket、不解析 DNS。输出应选仓库外的新目录，不使用历史 Evidence 目录。多次执行采用不同 UUID，不覆盖旧运行。

```powershell
$env:PYTHONPATH = 'src'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m p3_core.trusted_host --output D:\codex\p3-c3d-demo --mode good
```

将 mode 改为 auth、bola、rbac 分别演示单一缺陷；--fault 可选 deny、audit、missing_summary、before_send_revoke、partial_revoke。固定候选集合及合法对照均复用现有契约。模拟缺陷并不代表真实漏洞。

| 场景 | 预期 |
| --- | --- |
| good | 六个模拟 PASS；实际 request_count=0；完整 sidecar 后允许一次 Fixture 提交 |
| auth / bola / rbac | 对应 HTTP-N 检查模拟 FAIL，其余行为不改变；报告实际 API 结论仍 INCONCLUSIVE |
| deny | 未批准候选被 Controller DENY，不产生 action 或派发；拒绝仍消耗原预算 |
| audit | sidecar 写入故障，双端撤权，禁止后续派发与 Fixture 提交 |
| missing_summary | 缺口明确，不能用客户端成功冒充双端证据完成 |
| before_send_revoke | 模型派发计数为 0，但没有可信未派发证明，不提交 Fixture |
| partial_revoke | 模型派发计数为 1，不重复计数，缺少完整证据，不提交 Fixture |

测试见 [test_c3d_host.py](../tests/test_c3d_host.py)。包含绑定错配、旧实例、重复执行、并发单所有者、敏感字段、无根／无 sidecar、提交前故障和提交后审计失败。原 C-3C 并发提交与失败通知的确定性测试保留并全量重跑。

需求映射：REQ-001～009 为现有配置、权限矩阵及 Controller 的离线集成；REQ-010～012 为预算、撤权和安全停止复用；REQ-014～017 为分层结果、关联、脱敏及报告；REQ-018～019 为夹具与演示接口。REQ-013 的真实 HTTP、REQ-021 的真实策略实验和正式课程验收仍未完成，不能将此表解释为完整需求验收。

真实验收清单及全部 14 个 PENDING_AUTHORIZATION 状态原样保留；本演示没有提升这些状态的入口。
