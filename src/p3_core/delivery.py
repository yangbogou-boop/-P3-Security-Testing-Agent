"""Offline delivery CLI. No command activates a listener or live Executor."""
import argparse
import json
from pathlib import Path

from .experiments import run_scenario, compare_strategies, MODES, STRATEGIES, FAULTS
from .http.audit import verify_run
from .http.contract import HttpConfig


def integration_plan():
    return dict(network_status='PENDING_AUTHORIZATION', cases=[
        dict(case=name, status='PENDING_AUTHORIZATION') for name in (
            'GOOD_PAIRED_CONTROLS','AUTH_DISCLOSURE','BOLA_DISCLOSURE','RBAC_DISCLOSURE',
            'CONNECTION_FAILURE','UNEXPECTED_STATUS','INVALID_JSON','TRUNCATION',
            'TIMEOUT','REVOKE_CONNECT','REVOKE_FIRST_SEND','REVOKE_PARTIAL_SEND',
            'LATE_RESPONSE','AUDIT_FAILURE')],
        required=['Verified target-owner/delegate permission','Teacher catalog record',
                  'Exact version/scope binding','Trusted fixture supervisor'])


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, 'INVALID_ARGUMENTS: use --help; input values are not echoed.\n')


def main(argv=None):
    parser=SafeParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True,parser_class=SafeParser)
    sim=sub.add_parser('simulate');sim.add_argument('--mode',choices=MODES,default='good')
    sim.add_argument('--strategy',choices=STRATEGIES,default='fixed')
    sim.add_argument('--fault',choices=[f for f in FAULTS if f])
    sim.add_argument('--output',required=True)
    compare=sub.add_parser('compare');compare.add_argument('--output',required=True)
    compare.add_argument('--repeats',type=int,default=3)
    validate=sub.add_parser('validate');validate.add_argument('config')
    verify=sub.add_parser('verify');verify.add_argument('directory')
    sub.add_parser('network-plan')
    args=parser.parse_args(argv)
    try:
        if args.command=='simulate': result=run_scenario(args.mode,args.strategy,output=args.output,fault=args.fault)
        elif args.command=='compare':
            result=compare_strategies(args.output,args.repeats)
        elif args.command=='verify': result=verify_run(args.directory)
        elif args.command=='validate':
            def pairs(items):
                out={}
                for k,v in items:
                    if k in out: raise ValueError()
                    out[k]=v
                return out
            with Path(args.config).open('rb') as stream: data=stream.read(1048577)
            if len(data)>1048576: raise ValueError()
            cfg=HttpConfig.parse(json.loads(data,object_pairs_hook=pairs))
            result=dict(schema='VALID',scope_digest=cfg.scope_digest,network_status='PENDING_AUTHORIZATION')
        else: result=integration_plan()
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 1 if (result.get('integrity')=='INCOMPLETE_OR_INVALID' or
                     result.get('report',{}).get('audit_gap') or
                     result.get('report',{}).get('state')=='STOPPED') else 0
    except (OSError,ValueError,TypeError,KeyError):
        print(json.dumps(dict(error='INVALID_INPUT_OR_INCOMPLETE_OUTPUT',network_status='PENDING_AUTHORIZATION')))
        return 2


if __name__=='__main__':
    raise SystemExit(main())
