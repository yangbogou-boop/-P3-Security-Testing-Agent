"""Read-only, pinned evidence review calculator. Not a course grade or security score.

Semantic judgments are explicit reviewer records, not inferred from file existence.
Callers must pin the reviewed index hash independently of the evidence producer.
"""
import argparse
import hashlib
import json
import re
import stat
from pathlib import Path

RUBRIC_ID = 'P3-SELF-ASSESSMENT-001'
VERSION = '0.1'
# Approved conditions; immutable in the assessed repository's README/evidence.
DIMENSIONS = (
 ('D1','需求与Harness',((2,'范围与排除项一致'),(2,'需求GWT实现追踪'),(2,'开发与产品授权分离'))),
 ('D2','架构与约束',((3,'职责分离有实现依据'),(2,'取舍风险与重评条件'))),
 ('D3','功能与安全验证',((4,'Good及三种缺陷与对照'),(4,'拒绝及预算边界回归'),(3,'撤权终态竞态'),(3,'审计失败与有限结论'))),
 ('D4','变化与修复',((2,'问题反例与原因'),(2,'变更范围与版本'),(2,'修复后回归'),(2,'失败保留及恢复'))),
 ('D5','交接与发布',((2,'固定版本依赖入口可获取'),(2,'干净环境完整运行'),(2,'输出隔离重置恢复'),(2,'伙伴独立复现及差异'))),
 ('D6','治理与责任记录',((2,'决策状态限制与未决事项'),(2,'AI披露及实际责任记录'))),
 ('D7','工程实验与取舍',((3,'问题与共同条件'),(4,'逐次原始数据失败可复算'),(3,'成本单位范围缺测'),(3,'有限结论与本人取舍确认'),(2,'执行版本与环境绑定'))),
 ('D8','评价Agent与交叉审查',((4,'独立规则与需求适配'),(5,'三类校准与错误分析'),(2,'本人实际复核'),(2,'P1实际证据审查'),(2,'只读权限隐私边界'))),
 ('D9','个人能力',((8,'原理路径解释'),(8,'独立小任务'),(5,'工程取舍说明'),(4,'单人责任与AI边界确认'))),
)
HUMAN = {'D5.4','D6.2','D7.4','D8.3','D8.4','D9.1','D9.2','D9.3','D9.4'}

def rubric():
    return dict(id=RUBRIC_ID,version=VERSION,kind='CUSTOM_REFERENCE_NOT_COURSE_GRADE',
        dimensions=[dict(id=d,name=n,conditions=[dict(id=d+'.'+str(i),points=p,condition=t)
                     for i,(p,t) in enumerate(items,1)]) for d,n,items in DIMENSIONS])

def digest(data):
    return hashlib.sha256(data).hexdigest()

def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')

RUBRIC_SHA256 = digest(canonical(rubric()))
MAX_BYTES = 2 * 1024 * 1024

def read_local(path):
    path = Path(path)
    # Reject reparse/symlink components before following the final path.
    if str(path).startswith(('\\\\','//')) or '..' in path.parts:
        raise ValueError('UNSAFE_PATH')
    for item in (path, *path.parents):
        s=item.lstat()
        if stat.S_ISLNK(s.st_mode) or getattr(s,'st_file_attributes',0) & 1024:
            raise ValueError('UNSAFE_PATH')
    s=path.stat()
    if not stat.S_ISREG(s.st_mode) or s.st_size>MAX_BYTES: raise ValueError('INVALID_FILE')
    with path.open('rb') as f: data=f.read(MAX_BYTES+1)
    if len(data)>MAX_BYTES: raise ValueError('FILE_TOO_LARGE')
    return data

def parse(data):
    def pairs(items):
        out={}
        for k,v in items:
            if k in out: raise ValueError('DUPLICATE_KEY')
            out[k]=v
        return out
    return json.loads(data,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('NONFINITE')))

def assess(index_path, expected_index_sha256, target_commit):
    if not re.fullmatch('[0-9a-f]{40}',target_commit): raise ValueError('INVALID_COMMIT')
    raw=read_local(index_path)
    if digest(raw)!=expected_index_sha256: raise ValueError('INDEX_PIN_MISMATCH')
    index=parse(raw)
    if index['target_commit']!=target_commit or index['rubric_sha256']!=RUBRIC_SHA256:
        raise ValueError('VERSION_MISMATCH')
    rows=index['reviews']
    expected={c['id'] for d in rubric()['dimensions'] for c in d['conditions']}
    if not isinstance(rows,list) or len(rows)!=len(expected) or {r['id'] for r in rows}!=expected:
        raise ValueError('INVALID_CONDITION_SET')
    by_id={r['id']:r for r in rows}; dimensions=[]; snapshots={}
    for dim in rubric()['dimensions']:
        items=[]
        for cond in dim['conditions']:
            r=by_id[cond['id']]; state=r.get('status'); reasons=[]; refs=r.get('evidence',[])
            if state not in ('MET','NOT_MET','UNVERIFIED'): raise ValueError('INVALID_STATUS')
            if not isinstance(r.get('rationale'),str) or not r['rationale'].strip(): raise ValueError('MISSING_RATIONALE')
            if not isinstance(refs,list) or len(refs)>32: raise ValueError('INVALID_REFERENCES')
            if state!='UNVERIFIED' and not refs: reasons.append('MISSING_EVIDENCE')
            for ref in refs:
                try:
                    if ref['target_commit']!=target_commit: raise ValueError('WRONG_TARGET_VERSION')
                    if ref['evidence_version']!=target_commit and not ref.get('historical_limitation'):
                        raise ValueError('UNBOUND_HISTORICAL_VERSION')
                    data=read_local(ref['path'])
                    if digest(data)!=ref['sha256']: raise ValueError('HASH_MISMATCH')
                    quote=ref['quote']
                    if not isinstance(quote,str) or not quote.strip() or len(quote)>4096 or quote not in data.decode('utf-8-sig'):
                        raise ValueError('REFERENCE_NOT_FOUND')
                    if not ref.get('observation'): raise ValueError('MISSING_CONTENT_REVIEW')
                    snapshots[ref['path']]=data
                except (OSError,ValueError,KeyError,TypeError): reasons.append('INVALID_OR_MISSING_REFERENCE')
            # v0.1 never authenticates human ability or signatures from self-asserted JSON.
            if cond['id'] in HUMAN and state!='UNVERIFIED': reasons.append('HUMAN_VERIFICATION_NOT_SUPPORTED')
            if reasons: state='UNVERIFIED'
            items.append(dict(**cond,status=state,earned=cond['points'] if state=='MET' else 0,
                score=None if state=='UNVERIFIED' else cond['points'] if state=='MET' else 0,
                pending=cond['points'] if state=='UNVERIFIED' else 0,
                rationale=r['rationale'],validation_issues=reasons,evidence=refs))
        dimensions.append(dict(id=dim['id'],name=dim['name'],maximum=sum(c['points'] for c in items),
            earned=sum(c['earned'] for c in items),pending=sum(c['pending'] for c in items),conditions=items))
    if read_local(index_path)!=raw or any(read_local(p)!=b for p,b in snapshots.items()):
        raise ValueError('EVIDENCE_CHANGED')
    earned=sum(d['earned'] for d in dimensions); pending=sum(d['pending'] for d in dimensions)
    return dict(schema_version='p3-reference-self-assessment-v1',rubric_id=RUBRIC_ID,rubric_version=VERSION,
        rubric_sha256=RUBRIC_SHA256,index_sha256=expected_index_sha256,target_commit=target_commit,
        assessment_basis='PINNED_CONTENT_REVIEW_WITH_MACHINE_REFERENCE_CHECKS',
        semantic_judgments=index.get('reviewer_kind','UNSPECIFIED'),
        verified_subtotal=earned,maximum=100,assessed_max_points=100-pending,pending_max_points=pending,
        possible_score_range=[earned,earned+pending],reference_total=None if pending else earned,
        status='INCOMPLETE_ASSESSMENT' if pending else 'COMPLETE_REFERENCE_ASSESSMENT',dimensions=dimensions,
        human_signoff='pending',source_authenticated=False,course_grade=False,security_percentage=False,
        limitations=['Custom reference only; not teacher grade or release authorization.',
          'Pinned reviewer judgments are not independently authenticated semantic facts.',
          'Human criteria remain pending in v0.1; no fabricated ability or peer signoff.',
          'Offline evidence does not prove actual application or network safety.',
          'Historical execution versions are not upgraded to current execution proofs.'])

def render(report):
    lines=['# P3 项目参考自评（非课程成绩、非安全百分比）',
      '已核实得分：%s/100；已判定权重：%s；待核验权重：%s。' % (report['verified_subtotal'],report['assessed_max_points'],report['pending_max_points']),
      '可能得分区间：%s～%s。' % tuple(report['possible_score_range']),
      '完整参考总分：'+('暂不可完整评分' if report['reference_total'] is None else str(report['reference_total'])),
      'Git：'+report['target_commit'],'Rubric SHA-256：'+report['rubric_sha256']]
    for d in report['dimensions']:
        lines+=['','## %s %s：%s/%s，待核验%s' %(d['id'],d['name'],d['earned'],d['maximum'],d['pending'])]
        for c in d['conditions']:
            lines+=['- %s %s：%s；%s' %(c['id'],c['condition'],c['status'],json.dumps(c['rationale'],ensure_ascii=False))]
            for e in c['evidence']: lines+=['  - '+json.dumps(e,ensure_ascii=False)]
            if c['validation_issues']:lines+=['  - '+str(c['validation_issues'])]
    lines+=['','人工签署：pending。语义判断来源：'+str(report['semantic_judgments'])]+report['limitations']
    return '\n'.join(lines)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--index',required=True);p.add_argument('--index-sha256',required=True)
    p.add_argument('--target-commit',required=True);p.add_argument('--format',choices=('json','text'),default='json')
    a=p.parse_args(argv)
    try: r=assess(a.index,a.index_sha256,a.target_commit)
    except (OSError,ValueError,KeyError,TypeError,RecursionError):
        print(json.dumps(dict(error='INVALID_OR_CHANGED_ASSESSMENT_INPUT',reference_total=None)));return 2
    print(json.dumps(r,ensure_ascii=False,indent=2) if a.format=='json' else render(r));return 0

if __name__=='__main__':raise SystemExit(main())
