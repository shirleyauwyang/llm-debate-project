import collections,csv,json,math,statistics
from debate import SYSTEMS,wilson

def exact(b,c):
    n=b+c
    return min(1,2*sum(math.comb(n,i) for i in range(min(b,c)+1))/2**n) if n else 1.
def report(out):
    raw=json.loads((out/'results.json').read_text()); rows=raw['records']; names=list(SYSTEMS); dest=out/'analysis'; dest.mkdir(exist_ok=True)
    # Require all three configurations on the same questions, including partial runs.
    grouped=collections.defaultdict(dict)
    for r in rows: grouped[(r['dataset'],r['id'])][r['system']]=r
    complete={k:v for k,v in grouped.items() if set(v)==set(names)}
    rows=[r for k,v in complete.items() for r in v.values()]
    if not rows: raise ValueError('No questions with all three systems complete')
    summary=[]; comparisons=[]; transitions=[]; findings=[]; stage_audit=[]
    def table(name,rs):
        with open(dest/(name+'.csv'),'w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rs[0])); w.writeheader(); w.writerows(rs)
    for d in ['mmlu','gsm8k']:
        groups=[[r for r in rows if r['dataset']==d and r['system']==s] for s in names]
        if not groups[0]: continue
        acc=[]
        for s,rs in zip(names,groups):
            n=len(rs); k=sum(r['correct'] for r in rs); lo,hi=wilson(k,n); calls=[c for r in rs for st in r['stages'] for c in st]
            inp=sum(c['usage'].get('prompt_tokens',0) for c in calls); otp=sum(c['usage'].get('completion_tokens',0) for c in calls); usd=sum(r['cost'] for r in rs)
            summary.append(dict(dataset=d,system=s,n=n,correct=k,accuracy=100*k/n,error=100*(1-k/n),wilson_low=100*lo,wilson_high=100*hi,calls=len(calls),input_tokens=inp,output_tokens=otp,total_tokens=inp+otp,cost_usd=usd,unresolved=sum(r['unresolved'] for r in rs)))
            resolved = sum(not r['unresolved'] for r in rs)
            summary[-1].update(resolved_accuracy=100*k/resolved if resolved else None,
                               invalid_responses=sum(c['correctness']=='invalid' for c in calls),
                               truncations=sum(c['finish']=='length' for c in calls))
            for stage in range(len(rs[0]['stages'])):
                responses = [c for r in rs for c in r['stages'][stage]]
                outcomes = collections.Counter(c['correctness'] for c in responses)
                valid = outcomes['correct'] + outcomes['wrong']
                truncated = sum(c['finish']=='length' for c in responses)
                disagreement = sum(len({c['answer'] for c in r['stages'][stage]
                                        if c['answer'] is not None}) > 1 for r in rs)
                tokens_used = sorted(c['usage']['completion_tokens'] for c in responses)
                stage_audit.append(dict(dataset=d, system=s, stage=stage, responses=len(responses),
                    correct=outcomes['correct'], wrong=outcomes['wrong'], invalid=outcomes['invalid'],
                    invalid_rate=outcomes['invalid']/len(responses), truncated=truncated,
                    truncation_rate=truncated/len(responses),
                    primary_agent_accuracy=outcomes['correct']/len(responses),
                    valid_response_accuracy=outcomes['correct']/valid if valid else None,
                    questions_with_disagreement=disagreement, questions=len(rs),
                    completion_total=sum(tokens_used), completion_median=statistics.median(tokens_used),
                    completion_p95=tokens_used[math.ceil(.95*len(tokens_used))-1],
                    completion_max=max(tokens_used)))
            acc.append(100*k/n)
            for r in rs:
                for i in range(1,len(r['stages'])):
                    for a,c in enumerate(r['stages'][i]):
                        old=r['stages'][i-1][a]
                        before, after = old['correctness'], c['correctness']
                        label = before + '_to_' + after
                        transitions.append(dict(dataset=d, question_id=r['id'], system=s, agent=a+1,
                            from_round=i-1, to_round=i, truth=r['truth'], previous_audited_answer=old['answer'],
                            current_audited_answer=c['answer'], previous_correctness=before,
                            current_correctness=after, previous_valid=before!='invalid',
                            current_valid=after!='invalid', previous_invalid_reason=old['invalid_reason'],
                            current_invalid_reason=c['invalid_reason'],
                            change_status=('indeterminate' if 'invalid' in (before, after)
                                           else 'changed' if old['answer']!=c['answer'] else 'unchanged'),
                            transition_category=label))
            if 'Baseline' in names and s!='Baseline':
                base={r['id']:r for r in groups[0]}; cells=[0,0,0,0]
                for r in rs:
                    b=base[r['id']]['correct']; c=r['correct']; cells[0 if b and c else 1 if b else 2 if c else 3]+=1
                comparisons.append(dict(dataset=d,system=s,both_correct=cells[0],baseline_only=cells[1],debate_only=cells[2],both_incorrect=cells[3],p_unadjusted=exact(cells[1],cells[2])))
        best=[names[i] for i,a in enumerate(acc) if a==max(acc)]
        findings.append(f'{d}: highest observed accuracy {max(acc):.2f}%: {", ".join(best)}. Baseline {acc[0]:.2f}%. Differences versus Baseline (percentage points): '+', '.join(f'{s}: {a-acc[0]:+.2f}' for s,a in zip(names[1:],acc[1:])))
    table('summary',summary); table('mcnemar',comparisons) if comparisons else None
    if transitions:
        table('transitions',transitions)
        table('agent_answer_transitions',transitions)
        transition_counts=collections.Counter(
            (r['dataset'],r['system'],r['to_round'],r['transition_category']) for r in transitions)
        table('transition_counts',[dict(dataset=d,system=s,to_round=i,transition_category=c,count=n)
                                   for (d,s,i,c),n in sorted(transition_counts.items())])
    table('stage_audit',stage_audit)
    timing = out/'runtime.json'
    totals = {k: sum(r[k] for r in summary)
              for k in ('calls','input_tokens','output_tokens','total_tokens','cost_usd')}
    totals['active_seconds'] = json.loads(timing.read_text())['active_seconds'] if timing.exists() else None
    totals['mock'] = raw['mock']
    (dest/'run_totals.json').write_text(json.dumps(totals,indent=2))
    table('voting',[dict(dataset=r['dataset'],id=r['id'],system=r['system'],answer=r['answer'],unresolved=r['unresolved'],correct=r['correct']) for r in rows])
    (dest/'findings.md').write_text(('MOCK DATA — not research findings.\n' if raw['mock'] else '')+'\n\n'.join(findings)+'\n\nOnly questions completed by all systems are compared. Invalid answers count as incorrect. McNemar tests compare each debate configuration with Baseline. Identical initial prompts and temperature zero may reduce agent diversity. Hosted API outputs are not guaranteed deterministic. Compare A/B/C for round effects; debate agent count is fixed; cost increases structurally with rounds and agents. Inspect transitions.csv for harmful and beneficial revisions. Estimates exclude unknown billed retries.')
