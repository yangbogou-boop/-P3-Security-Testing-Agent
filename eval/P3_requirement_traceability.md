# P3 需求—测试—证据追踪（2026-10-19）

[RC2](../brief/P3_specification_v1.0-rc2.md) 为规范基线；本表不修改 ID 或强度。没有真实 HTTP 或正式课程验收通过声明。158 项为本地无网络测试数量，并非 158 个 GWT 全项通过。

| 稳定 ID | 强度 | 原 GWT | 当前实现／验证状态 | 可定位自动化测试 |
| --- | --- | --- | --- | --- |
| P3-REQ-001 | MUST | GWT-N01 | 离线子场景通过；真实集成待授权 | `test_preflight_fail_has_no_plan_or_io` |
| P3-REQ-002 | MUST | GWT-P01、GWT-A02 | 离线子场景通过；真实集成待授权 | `test_synthetic_permission_cannot_start_live_run` |
| P3-REQ-003 | MUST | GWT-P04、GWT-P05 | 离线子场景通过；真实集成待授权 | `test_strategy_repeatable / test_strategy_evidence_changes_next_choice` |
| P3-REQ-004 | MUST | GWT-P02、GWT-N02 | 离线子场景通过；真实集成待授权 | `test_three_defects_both_strategies` |
| P3-REQ-005 | MUST | GWT-P02、GWT-N02 | 离线子场景通过；真实集成待授权 | `test_three_defects_both_strategies` |
| P3-REQ-006 | MUST | GWT-P02、GWT-N02 | 离线子场景通过；真实集成待授权 | `test_three_defects_both_strategies` |
| P3-REQ-007 | MUST | GWT-A01、GWT-A02 | 离线子场景通过；真实集成待授权 | `test_bad_selector_fails_closed / test_transport_constructor_has_no_io_and_requires_current_object` |
| P3-REQ-008 | MUST | GWT-N03 | 离线子场景通过；真实集成待授权 | `test_adapter_rejects_header_and_target_mutations` |
| P3-REQ-009 | MUST | GWT-A01 | 离线子场景通过；真实集成待授权 | `test_late_response_during_read_cannot_upgrade` |
| P3-REQ-010 | MUST | GWT-N04、GWT-N05、GWT-A01 | 离线子场景通过；真实集成待授权 | `test_denials_consume_budget_and_eighth_ninth_boundary / test_gwt_a01_a_repeat_stops_only_exhausted_valuable_work` |
| P3-REQ-011 | MUST | GWT-A03 | 离线子场景通过；真实集成待授权 | `test_t28_send_return_and_count_are_one_gate_transaction / test_partial_send_then_revocation_retains_one_model_send` |
| P3-REQ-012 | MUST | GWT-N01、GWT-N05、GWT-N06 | 离线子场景通过；真实集成待授权 | `test_faults_do_not_confirm_leaks / test_audit_capacity_fails_closed` |
| P3-REQ-013 | MUST | GWT-P01、GWT-N06 | 静态传输组件＋假 socket 测试；真实请求／响应未执行 | `test_transport_methods_with_fake_socket_only` |
| P3-REQ-014 | MUST | GWT-P01、GWT-P02、GWT-N02、GWT-N07 | 离线子场景通过；真实集成待授权 | `test_disk_evidence_integrity_and_no_tokens / test_header_timeout_model_never_claims_actual_execution` |
| P3-REQ-015 | MUST | GWT-P03、GWT-N03、GWT-A03 | 离线子场景通过；真实集成待授权 | `test_unique_ids_and_no_overwrite / test_report_tamper_rejected` |
| P3-REQ-016 | MUST | GWT-P03、GWT-N07 | 离线子场景通过；真实集成待授权 | `test_artifacts_never_contain_credentials_parameters_or_exception_body` |
| P3-REQ-017 | MUST | GWT-N04、GWT-N07、GWT-A03 | 离线子场景通过；真实集成待授权 | `test_faults_do_not_confirm_leaks` |
| P3-REQ-018 | MUST | GWT-P02、GWT-N02、GWT-P04 | 离线子场景通过；真实集成待授权 | `test_entire_declared_matrix_and_single_defect_isolation` |
| P3-REQ-019 | SHOULD | GWT-P04、GWT-N01 | 离线子场景通过；真实集成待授权 | `test_cli_validate_does_not_grant_permission / test_cli_network_plan_pending` |
| P3-REQ-020 | MUST | GWT-P04 | 离线子场景通过；真实集成待授权 | `test_comparison_records_actual_observations` |
| P3-REQ-021 | MUST | GWT-P05 | 36 次离线比较完成；ADR Proposed，真实比较／正式验收待办 | `test_comparison_records_actual_observations` |
| P3-REQ-022 | MAY | GWT-A04（后续） | 未实施，保持可选 | 未接入（MAY） |

## 证据定位与限制

- 原离线控制测试：[test_core.py](../tests/test_core.py)，49 项；无网络 HTTP：[test_http_core.py](../tests/test_http_core.py)，54 项；业务夹具：[test_mock_api.py](../tests/test_mock_api.py)，24 项。
- 本轮 [test_remaining.py](../tests/test_remaining.py)，31 项；测试均阻断真实 socket，低层传输测试只用 FakeSocket，未构造真实许可并派发。
- 策略逐次记录：[P3_offline_strategy_results.json](P3_offline_strategy_results.json)，36 个独立 run_id；每条包含逻辑实验口径、三计数／模型计数、分子分母、故障和时间。run_id 对应独立交付包中的 JSONL／Manifest／报告。
- HTTP-T27～T35 的原确定性测试继续通过；新增分段发送、恢复 unknown、响应头／正文区分、绑定错误凭据及证据篡改检查。没有将无网络子场景升级为真实 HTTP-T 验收。
- GWT-A01-a/b/c 保留原测试；动态策略对 MISSING_CONTROL 优先补必要对照，不提前停止正常检查。
- [C-3 清单](P3_http_integration_status.json) 全部真实网络场景为 PENDING_AUTHORIZATION。REQ-013、真实撤权／超时资源回收、REQ-021 实际成本及正式验收未完成。
- 没有真实 LLM 或 Token 用量；准备和人工复核时间未测。模型 FAIL 只表示合成夹具判定，不是现实漏洞报告。

## C-3A/B 离线加固补充（基线 30c98db）

新增 [test_c3_preflight.py](../tests/test_c3_preflight.py) 24 项，本地共 182 项通过；上面的 158 项为前轮基线，不删除或替代原有测试。REQ-007／009／011／012：服务端非阻塞发送与撤权共用短 gate，等待及关闭在门外；REQ-010／015：正发送计数 hook、部分发送、预算到点与恢复记录仍由原控制规则约束；REQ-014／016／017：审计失败、错误绑定、最小摘要和关闭失败明确呈现，不新增确认性安全结论。

服务端新增确定性用例覆盖撤权先／后赢、等待不阻塞撤权、部分发送、到期／超时、旧凭据、错实例与清理失败。真实分支计数 hook 的内存插桩不生成持久化 Evidence，不声称真实请求发生。全部实际 HTTP 场景仍待授权，见 [许可核验与 14 项验收卡](P3_c3_authorization_checklist.md) 和 [本轮审核报告](../review/P3_c3_preflight_review.md)。未变更 RC2 ID／强度，ADR-005 仍 Proposed。
