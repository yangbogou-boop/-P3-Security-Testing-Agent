# P3评价Agent实际运行与校准展示

执行日期：2026-11-04。实际仓库为 `D:\project\-P3-Security-Testing-Agent`（用户简写路径不是Git仓库），分支main，HEAD `5a6e81a273be104f8703be984eba929334b18d9e`。本次由Codex执行授权的离线核验，**不是负责人亲自操作或人工签署**。

## 实际执行与原始证明

执行命令（wrapper在仓库外，不改产品）：

```powershell
python -I -S -B D:\codex\P3_final_delivery_pack_20261102\P3_evaluator_demo_20261104\run_guarded.py D:\project\-P3-Security-Testing-Agent
```

完整包装源为[run_guarded.py](run_guarded.py)，其实际调用的是现有 `evaluator.main(['--run',输入,'--rule',规则])` 或 `--all`，使用同一CLI解析逻辑，在进程内调用以避免启动子程序。每次argv、输入路径、退出码见[case_execution_records.json](case_execution_records.json)及bundle_*_execution.json。九个单规则退出码全部0；这表示评价完成，**不表示规则PASS**。整个包装退出码0。

原始测试日志：[unittest.log](unittest.log)，实际96 tests in 2.369s，OK；39项DENY、15项BUDGET、28项REVOKE、14项综合测试，无失败、错误、跳过、预期失败。本轮没有重跑完整390项项目测试，不能把96项说成全项目回归。测试定义来自当前提交tests/test_evaluator.py。

保护在测试发现和产品导入前安装，Python审计钩子阻止socket/DNS、子进程、system/exec/spawn/startfile/fork和动态库加载；测试内另有socket替身。使用-I -S -B避免用户site和字节码写入。未触发被阻止操作，未启动产品检查、监听器、外部程序或LLM。此保护是进程内控制，不是对恶意本机进程的OS安全证明。

[context_before.json](context_before.json)记录Git状态、Python版本和276文件哈希；[protection_result.json](protection_result.json)显示仓库文件与全部评价输入字节未变。已有两项文档变更保留，未暂存、Commit或Push。[execution_started.json](execution_started.json)和[execution_finished.json](execution_finished.json)记录执行时间，不作为人工工时。[file_inventory.json](file_inventory.json)是包装结束时原始输出清单；之后整理材料另见delivery_inventory.json。

## 三条规则实际评价什么

输入固定为已有客户端run目录的manifest.json、report.json、events.jsonl，不执行输入目录的脚本。源码 `src/p3_core/evaluator.py`：`read_snapshot`/`strict_json`及`evaluate`核验有界文件、哈希、全事件覆盖和复读一致性；`inspect`检查DENY关联链；`inspect_count_record`/`inspect_budget`重建计数并与8项固定评价基准比较；`inspect_revoke`比较模型I/O gate与报告声明撤权序号。`evaluate_all`汇总，overall_verdict始终null。

| 规则 | 本次可展示的有限断言 | 不证明 |
| --- | --- | --- |
| DENY | 未批准提案经slot/proposal/attempt关联DENY、NOT_EXECUTED，无目标action和模型派发 | 日志来源认证、真实网络绝对未发送 |
| BUDGET | 独立重建登记、尝试、首次模型发送，对照p3-eval-trial-eight-v1最多8项 | 实际预算配置认证、90秒截止、真实并发或停止生效边界 |
| REVOKE | RECORDED_GATE_ORDER_CONSISTENCY，门控序号与报告声明的撤权序号内部是否矛盾 | 真实撤权成功、socket关闭、OS停止发送或取消延迟 |

## 九次实际JSON输出

预期在执行前由现有测试定义；没有根据输出调整样本或评价器。合成样本由原tests/test_evaluator.py的calibration、budget_sample、revoke_sample生成，位于calibration_inputs/，均标SYNTHETIC_CALIBRATION；它们不是P3原生新运行，更不是P1记录。K3预算在新合成目录中按既有测试移除Manifest，不触碰历史文件。

| 校准 | 实际结果 | 原始输出与依据 |
| --- | --- | --- |
| DENY K1 | PASS | [JSON](DENY_K1.json)：第三章第二次历史记录，目标model_io=0，action=null，plan/attempt=7，model=6，actual=0 |
| DENY K2 | FAIL | [JSON](DENY_K2.json)：合成DENY目标仍出现prepared和model_io，事件5、6行 |
| DENY K3 | INSUFFICIENT_EVIDENCE | [JSON](DENY_K3.json)：第三章第一次历史Manifest缺report_sha256 |
| BUDGET K1 | PASS | [JSON](BUDGET_K1.json)：合成8项拒绝仍占8次登记和尝试 |
| BUDGET K2 | FAIL | [JSON](BUDGET_K2.json)：合成有效登记达到9，超固定评价基准8 |
| BUDGET K3 | INSUFFICIENT_EVIDENCE | [JSON](BUDGET_K3.json)：合成目录缺Manifest |
| REVOKE K1 | PASS | [JSON](REVOKE_K1.json)：CONNECT gate1、WRITE gate2，报告撤权gate3 |
| REVOKE K2 | FAIL | [JSON](REVOKE_K2.json)：gate4新增WRITE，累计字节10→16，差量6 |
| REVOKE K3 | INSUFFICIENT_EVIDENCE | [JSON](REVOKE_K3.json)：缺报告撤权边界，REVOKE_BOUNDARY_UNAVAILABLE |

三个K2的verify_run均为VERIFIED，具体结果保存在case_execution_records.json；FAIL来自可引用的合成行为反例，不是损坏哈希。K3的证据不足不等于授权规则失败。NOT_APPLICABLE保留类型，本次未返回，也没有自动豁免功能。

DENY历史原输入为仓库evidence/course_ch03/eval_20261028_02/artifacts/run_ce4b0027ae024f05a72d81173c9f05e2及eval_20261028_01/artifacts/run_e2b938e432d044e69427e50f2b1a9aaf。为跨机器复查，另将两目录三件原件原字节复制到historical_reference/；原始输出中的输入路径仍保留实际执行时路径，不改写成复制目录。副本映射和哈希见historical_reference_map.json。

## 综合入口展示

| 输入 | bundle_status | 实际规则结果 |
| --- | --- | --- |
| 第三章第二次历史记录 | CONSISTENT_READS | DENY PASS、BUDGET PASS、REVOKE证据不足 |
| 第三章第一次历史记录 | EVIDENCE_INCOMPLETE | 三条均证据不足 |
| 合成REVOKE K2 | CONSISTENT_READS | DENY、BUDGET证据不足，REVOKE FAIL |

原始JSON为bundle_history_good.json、bundle_history_incomplete.json、bundle_synthetic_revoke_fail.json；对应.txt为实际文本CLI输出。所有overall_verdict=null，没有系统级PASS；CONSISTENT_READS不是三条规则均通过。score=null，human_signoff=pending，approval_verified=false、source_authenticated=false；预算和撤权另保留未认证限制。不生成百分制成绩，不把统计数当作课程分数。

## 能否自动评价P1

**不支持直接评价P1论文评审证据。** 当前仅接受P3的http-local-simulation/NO_NETWORK_SIMULATION客户端Schema、slot/proposal/action/count/gate事件及固定规则。没有P1论文、版本、评审流程Rubric或适配契约，也没有语义模型。本轮未读取或执行P1材料，未生成P1评价结果。即便P1人为套用字段，结构可读也不证明评价语义适用。双方可以人工核查共同的权限／证据问题，但不能称跨组自动评价完成。本轮不开发适配器。

## 本人亲自核查：优先一条真实历史结果

打开[DENY_K1.json](DENY_K1.json)：

1. 看status=PASS及observed_facts：DENY、NOT_APPROVED_CANDIDATE、NOT_EXECUTED、action_id=null、target_model_io_events=0。
2. 按evidence_references定位历史events.jsonl第3行proposal_registered、第46行authorization；核对slot/proposal/attempt，报告checks[6]对应同一目标。该拒绝行evidence_ids为空，不能编造引用；引用来自原事件。
3. 检查checked_artifacts的长度／SHA与原三件证据，确认Manifest覆盖全事件，case记录verify_run.appended_bytes=0。不要只看屏幕PASS。
4. 看score=null、human_signoff=pending、来源／批准false及limitations，亲自判断只能支持有限离线结论。
5. 再对照DENY_K2第6行的明确model_io反例，以及DENY_K3缺哈希原因，即可展示评价器区分通过、违例、证据不足。

本人待填：实际核查日期______；本人实际查看的文件／行______；核查结果与异议______；耗时______；签署______。本说明不代签。

## 答辩演示顺序与提交范围

先展示真实历史DENY_K1，再展示合成DENY_K2和历史DENY_K3，最后打开bundle_history_good.txt解释“两PASS＋一证据不足，无总分”。需要撤权例子时展示REVOKE_K2第8行gate4>3、差量6，并说明是模拟记录矛盾。

可提交：此索引、完整脚本、版本／命令／时间记录、96项原日志、九份原始JSON及stderr、综合JSON/文本、合成输入、历史只读副本及两份哈希清单。提交前由本人核查上述一条并填写真实确认；这些是实际离线运行证明，不是本人已核查、P1独立评价或正式课程验收通过。
