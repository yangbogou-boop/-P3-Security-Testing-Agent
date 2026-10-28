# 第二次执行前约定

2026-10-28。第一次运行及失败目录 eval_20261028_01 原样保留。此次使用 HEAD 67242ba5e0d71e6d2cfd3911ec758085760d1e79 加未提交源码修复与新测试；执行代码差异和逐文件 SHA-256 见 execution_code_diff.patch／execution_context.json，不能称作未修改 HEAD。

复用第一次的规则、输入及业务判定标准：Good、fault=deny，复制 HTTP-C-AUTH，仅将 check_id 改为 unapproved；批准的六项候选可以内存派发，被拒项应 DENY／NOT_EXECUTED／INCONCLUSIVE、无 action，拒绝事件可关联。最终三计数为 7／7／0，模型计数 6。

新增契约验收：现有 verify_run 对新客户端目录必须返回 VERIFIED 且 approval_verified=false；报告哈希采用现有 BoundedEvidence 的脱敏后、sort_keys=True、ensure_ascii=False、allow_nan=False UTF-8 序列化，不修改核验器。sidecar 独立检查应保留 SOURCE_UNVERIFIED，不将 lifecycle 套用客户端契约。

先进行正常证据回归的修复前失败复现及修复后七项精准测试，再运行原 Host 定点测试与一次持久化演示，最后全量无网络套件。每次在项目导入／discovery 前安装原审计拦截，使用 python -I -S -B -；这是进程级保护，不是 OS 隔离。所有执行日志保存，任何失败不删除。

脱敏检查仍逐值搜索当前持有的模拟凭据；头部字面量检查只扫描产品 artifacts 及 Host 返回结果，避免将命令中的检测字符串误当泄漏。原始失败检查不改，扫描对象区别在执行前明示。不创建真实授权，不接入网络或真实 LLM，14 项实际验收仍待授权。
