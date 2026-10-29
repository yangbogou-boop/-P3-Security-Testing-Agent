# P3 伙伴独立复现交接草案

状态：**NOT_YET_REPRODUCED_BY_PEER**。2026-10-28 仅准备说明，没有运行以下命令，不能标“已试跑”，不填写伙伴姓名、时间、签名或成功结果。

## 范围与版本

指定已有工程版本 `5c16b2bd6d204719692d03a925bd733c9852140a`，Python 3.9+ 标准库。先由伙伴检查 `git rev-parse HEAD`、`git status --short`、`python --version`；版本不符或代码不干净时先记录并澄清，不 reset／clean。原组历史实验没有完整绑定执行代码 SHA；本次指定版本仅供未来复现，不能伪称历史复刻环境完全相同。

最小对象：**BOLA 模式的一次 fixed 和一次 dynamic**。相同六候选、矩阵、预算；每次独立 Fixture，合成凭据。比较两策略的覆盖／检出及模型请求数，不新建服务器，不需要 API Key，不调用真实 LLM。原组同条件各三次见[实验报告](../eval/P3_engineering_experiment.md)和[原JSON](../eval/P3_offline_strategy_results.json)；伙伴两次新结果单独保存，不替代原36次，不用于统计优越性。

## 仓库内原组证据（第二轮归档更新）

原组36次历史运行的108个原始文件已按原字节归档，见[逐次索引](../evidence/course_ch04/strategy_history_36/README.md)、[归档清单](../evidence/course_ch04/strategy_history_36/archive_manifest.json)及[派生统计](../eval/P3_strategy_recalculation.json)。无需个人磁盘路径。代码复现版本仍为上述5c16b2b；材料第一轮由9754048纳入，本轮归档待审核提交，负责人应提供包含本归档的实际交付提交号，不能指定尚未生成的SHA。代码与材料版本各自记录；历史执行SHA仍NOT_FULLY_BOUND。

## 执行前确认

伙伴和负责人确认此次离线复现范围，审查现有 [CLI](../src/p3_core/delivery.py)、[模拟入口](../src/p3_core/experiments.py)及下方命令；不运行不明脚本，不启用 live/service。授权仅限内存模拟，不能把 synthetic_registry 当作真实许可。所有来源文件和旧证据只读。

以下是静态核对现有接口后的**待实际验证命令草案**。在指定版本仓库根目录 PowerShell 中运行。新证据目录使用 GUID；命令中的审计钩子在项目导入前拒绝 socket、DNS、外部执行及动态库加载，是进程内保护，不是系统级隔离。发现阻断或异常保留日志并停止，不自动更换版本或移除保护。

```powershell
$peerOut = Join-Path $env:TEMP ('P3-peer-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $peerOut | Out-Null
git rev-parse HEAD | Out-File -Encoding utf8 (Join-Path $peerOut 'git-head.txt')
git status --short | Out-File -Encoding utf8 (Join-Path $peerOut 'git-status.txt')
@'
import sys
def guard(event, args):
    if event.startswith('socket.') or event in ('subprocess.Popen','os.system','os.exec','os.posix_spawn','ctypes.dlopen'):
        raise RuntimeError('NETWORK_OR_EXTERNAL_EXECUTION_FORBIDDEN')
sys.addaudithook(guard)
import json, platform, datetime, contextlib
from pathlib import Path
out = Path(sys.argv[1])
sys.path.insert(0, str(Path.cwd() / 'src'))
with (out/'environment.json').open('x', encoding='utf-8') as f:
    json.dump(dict(python=sys.version, platform=platform.platform(),
                   started_at=datetime.datetime.now(datetime.timezone.utc).isoformat()), f, indent=2)
with (out/'execution_stderr.txt').open('x', encoding='utf-8') as err, contextlib.redirect_stderr(err):
    from p3_core.delivery import main
    for strategy in ('fixed','dynamic'):
        with (out/(strategy+'.json')).open('x', encoding='utf-8') as result, contextlib.redirect_stdout(result):
            code = main(['simulate','--mode','bola','--strategy',strategy,'--output',str(out/'runs')])
        with (out/(strategy+'-exit.json')).open('x', encoding='utf-8') as f:
            json.dump(dict(exit_code=code, finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat()), f)
        if code != 0:
            raise SystemExit(code)
'@ | python -I -S -B - $peerOut
$peerExit = $LASTEXITCODE
Write-Output ('Python exit code: ' + $peerExit)
Write-Output ('Evidence directory: ' + $peerOut)
```

伙伴另保存实际使用的完整命令、终端错误、代码版本和任何本地差异；不要只保存屏幕上的成功行。若 Python 启动失败，可能没有完整 JSON，照实记 NOT_EXECUTED／失败原因，不生成替代结果。不追加真实目标地址或任何额外服务调用。

## 预期检查及独立结论

读取各自的新 fixed.json／dynamic.json：应标 NO_NETWORK_SIMULATION，覆盖6/6，BOLA检出1/1，误确认0，model_requests=6，actual_requests=0，llm_calls=0；正常路径 COMPLETED。检查实际结果而不是照抄预期；缺陷只表现为 simulated_conclusion=FAIL，实际 execution=NOT_EXECUTED、conclusion=INCONCLUSIVE。

核查 report.run_id 对应 runs 子目录的 JSONL、Manifest、Report，integrity 应是现有 verify_run 的内部一致性返回，不是批准真实性。缺失文件、audit_gap、意外网络保护触发或结果不同均应停止确认并写差异。两次内存执行先后仍可能影响时间；单次结果不支持性能优越性。不要把 local_elapsed 和 planning 相加。

保持原始字节和失败文件不变，记录每个产物的字节数、SHA-256；复制给原组前扫描敏感内容并核验复制哈希。若需要脱敏副本，原始件保留，另列变换范围，不能把副本冒充原始件。不要随意经 Git 文本换行转换搬运原始 JSONL；归档／属性处理先审核。

伙伴独立填写：实际版本、环境、命令、两个 run_id、实际指标、异常／求助、支持与未覆盖范围。操作人与判断者由真实参与者填写，原组不代跑后请其签字。无法执行时写 NOT_EXECUTED 和原因；仅阅读认可仍不算独立复现。一次最小比较即使通过，也不等于原36次全部重现、正式课程验收或真实HTTP许可。
