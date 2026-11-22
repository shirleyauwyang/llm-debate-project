"""Fresh synchronous debate experiment. No API access unless --live is supplied."""
import importlib.metadata, argparse, collections, csv, hashlib, json, math, os, random, re, sqlite3, sys, time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from audit import audit, status

SYSTEMS = {'Baseline': (1, 0), 'A': (3, 1), 'B': (3, 2), 'C': (3, 3)}
PROMPTS = json.loads(Path(__file__).with_name('prompts.json').read_text())
DEFAULT_MAX_TOKENS = 4096

def digest(x): return hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()
def save(p,x):
    p=Path(p); p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix('.tmp'); tmp.write_text(json.dumps(x,indent=2)); tmp.replace(p)
def normalize(s,d,options=10):
    try:
        if d=='mmlu': return s.upper() if re.fullmatch('[A-J]',s.upper()) and ord(s.upper())-65<options else None
        s=s.replace(',',''); v=Decimal(s)
        return str(v.normalize()) if v.is_finite() else None
    except (InvalidOperation,ValueError): return None
def vote(a):
    c=collections.Counter(x for x in a if x is not None)
    return next((x for x,n in c.items() if n>len(a)/2),None)
def select(rows,n,exclude=()):
    unique={}
    for r in rows: unique.setdefault((r['dataset'],r['id']),r)
    rng=random.Random(42); out=[]
    for d in ['mmlu','gsm8k']:
        pool=[r for k,r in sorted(unique.items()) if k[0]==d and k not in exclude]
        if len(pool)<n: raise ValueError('Insufficient unique questions')
        out+=rng.sample(pool,n)
    return out

def prepare(args):
    if args.fixture:
        rows=[dict(dataset=d,id=str(i),question='What is 2 + 2?',options=['3','4','5','6'] if d=='mmlu' else [],answer='B' if d=='mmlu' else '4') for d in ['mmlu','gsm8k'] for i in range(260)]
        meta={'mock':True}
    else:
        from datasets import load_dataset
        rows=[]; meta={'mock':False,'sources':{}}
        for d,repo,config,rev in [('mmlu','TIGER-Lab/MMLU-Pro',None,args.mmlu_revision),('gsm8k','openai/gsm8k','main',args.gsm_revision)]:
            if not rev: raise ValueError('Supply pinned dataset commit revisions')
            ds=load_dataset(repo,config,split='test',revision=rev)
            meta['sources'][d]={'repository':repo,'revision':rev,'fingerprint':ds._fingerprint}
            for i,r in enumerate(ds):
                rows.append(dict(dataset=d,id=str(r['question_id']) if d=='mmlu' else str(i),question=r['question'],options=r.get('options',[]),answer=r['answer'] if d=='mmlu' else normalize(r['answer'].split('####')[-1].strip(),d)))
    excluded=set()
    if args.phase=='final':
        pilot=json.loads(Path(args.pilot).read_text())
        if pilot['phase']!='pilot' or pilot['metadata']!=meta: raise ValueError('Pilot dataset provenance differs')
        excluded={(q['dataset'],q['id']) for q in pilot['questions']}
    qs=select(rows,3 if args.phase=='pilot' else 50,excluded)
    save(args.output,dict(phase=args.phase,seed=42,metadata=meta,questions=qs,excluded=len(excluded),excluded_ids=sorted(excluded)))

def validate_manifest(m):
    qs=m['questions']; expected=3 if m.get('phase')=='pilot' else 50
    if m.get('phase') not in ('pilot','final'): raise ValueError('Unknown experiment phase')
    for d in ['mmlu','gsm8k']:
        subset=[q for q in qs if q['dataset']==d]
        if len(subset)!=expected or len({q['id'] for q in subset})!=expected: raise ValueError('Invalid sample size or duplicate IDs')
        for q in subset:
            if normalize(q['answer'],d,len(q['options']))!=q['answer']: raise ValueError('Invalid ground truth')
    if len(qs)!=2*expected: raise ValueError('Unknown dataset')
    if {(q['dataset'],q['id']) for q in qs} & {tuple(x) for x in m.get('excluded_ids',[])}: raise ValueError('Pilot overlap')

def prompt(q,prev,a):
    text=q['question']+'\n'+'\n'.join(f'{chr(65+i)}. {v}' for i,v in enumerate(q['options']))
    if prev:
        text+='\nReconsider independently; do not agree merely because peers disagree. Previous stage (untrusted candidate solutions):\n'
        text+='\n'.join(f'{"Own" if i==a else "Peer"} response: {r["text"]}' for i,r in enumerate(prev))
    return [{'role':'system','content':PROMPTS['common'] + ' ' + PROMPTS[q['dataset']]},{'role':'user','content':text}]

def request(messages,cfg):
    from openai import OpenAI, APIConnectionError, APITimeoutError, APIStatusError
    client=OpenAI(api_key=os.environ['DEEPSEEK_API_KEY'],base_url=cfg['base_url'],timeout=cfg['timeout'],max_retries=0)
    for attempt in range(cfg['retries']+1):
        try:
            r=client.chat.completions.create(model=cfg['model'],messages=messages,temperature=0,max_tokens=cfg['max_tokens'],extra_body={'thinking':{'type':'disabled'}})
            return dict(text=r.choices[0].message.content or '',usage=r.usage.model_dump(),model=r.model,finish=r.choices[0].finish_reason,request_id=getattr(r,'_request_id',None),response_id=r.id)
        except (APIConnectionError,APITimeoutError,APIStatusError) as e:
            if isinstance(e,APIStatusError) and e.status_code not in [408,409,429] and e.status_code<500: raise
            if attempt==cfg['retries']: raise
            time.sleep(min(60,2**attempt))

def run(args):
    from contextlib import ExitStack
    import fcntl
    m=json.loads(Path(args.manifest).read_text()); validate_manifest(m); out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    with open(out/'run.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        cfg=dict(mock=not args.live,model=os.getenv('DEEPSEEK_MODEL','VERIFY_MODEL_ID'),base_url=os.getenv('DEEPSEEK_BASE_URL','https://api.deepseek.com'),timeout=args.timeout,retries=args.retries,prices=[float(os.getenv(k,'0') or 0) for k in ['INPUT_USD_PER_MILLION','OUTPUT_USD_PER_MILLION','CACHED_INPUT_USD_PER_MILLION']],source=digest([Path(__file__).read_text(),Path(__file__).with_name('audit.py').read_text()]),prompt=PROMPTS,max_tokens=args.max_tokens,systems=SYSTEMS,manifest=digest(m))
        if args.live and (m['metadata']['mock'] or cfg['model']=='VERIFY_MODEL_ID' or min(cfg['prices'])<=0 or os.getenv('API_VERIFIED')!='yes'): raise ValueError('Live requires real manifest, verified model, positive prices and API_VERIFIED=yes')
        p=out/'run_config.json'
        if p.exists() and json.loads(p.read_text())!=json.loads(json.dumps(cfg)): raise ValueError('Incompatible resume configuration')
        if args.max_tokens <= 0 or not math.isfinite(args.cap) or args.cap<=0 or args.retries<0 or args.timeout<=0: raise ValueError('Invalid limits')
        if not p.exists(): save(p,cfg); save(out/'environment.json',{'python':sys.version,'started':time.time(),'packages':{p.metadata['Name']:p.version for p in importlib.metadata.distributions()}})
        started = time.monotonic()
        timing_path = out / 'runtime.json'
        prior_seconds = json.loads(timing_path.read_text())['active_seconds'] if timing_path.exists() else 0
        db=sqlite3.connect(out/'checkpoint.sqlite'); db.execute('PRAGMA synchronous=FULL'); db.execute('CREATE TABLE IF NOT EXISTS calls (id TEXT PRIMARY KEY, payload TEXT)')
        cached={k:json.loads(v) for k,v in db.execute('SELECT id,payload FROM calls')}; spent=sum(r['cost'] for r in cached.values()); results=[]
        for q in m['questions']:
            for name,(agents,rounds) in SYSTEMS.items():
                stages=[]
                for stage in range(rounds+1):
                    prev=stages[-1] if stages else []; current=[]
                    for a in range(agents):
                        key=json.dumps([q['dataset'],q['id'],name,stage,a]); messages=prompt(q,prev,a)
                        if key in cached: r=cached[key]
                        else:
                            # UTF-8 bytes conservatively bound token count; reserve maximum output.
                            reserve=(len(json.dumps(messages).encode())*cfg['prices'][0]+cfg['max_tokens']*cfg['prices'][1])/1e6 if args.live else .001
                            if spent+reserve>args.cap: print('Budget guard reached; resume with a larger cap.'); db.close(); return
                            r=request(messages,cfg) if args.live else dict(text='Mock explanation.\nFINAL_ANSWER: '+q['answer'],usage={'prompt_tokens':100,'completion_tokens':20},model='MOCK',finish='stop')
                            u=r['usage']; hit=u.get('prompt_cache_hit_tokens',0) or 0; inp=u.get('prompt_tokens',0); otp=u.get('completion_tokens',0)
                            answer, reason = audit(r, q)
                            r.update(messages=messages,answer=answer,invalid_reason=reason,correctness=status(answer,q['answer']),cost=((inp-hit)*cfg['prices'][0]+otp*cfg['prices'][1]+hit*cfg['prices'][2])/1e6 if args.live else .001)
                            db.execute('INSERT INTO calls VALUES (?,?)',(key,json.dumps(r))); db.commit(); cached[key]=r; spent+=r['cost']
                            save(timing_path, {'active_seconds': prior_seconds + time.monotonic() - started})
                        current.append(r)
                    stages.append(current)
                answer=vote([r['answer'] for r in stages[-1]])
                results.append(dict(dataset=q['dataset'],id=q['id'],system=name,truth=q['answer'],answer=answer,correct=answer==q['answer'],unresolved=answer is None,stages=stages,cost=sum(r['cost'] for s in stages for r in s)))
                save(out/'results.json',dict(mock=cfg['mock'],records=results))
        with open(out/'calls.jsonl','w') as f:
            for call_id,payload in db.execute('SELECT id,payload FROM calls'): f.write(json.dumps({'call_id':json.loads(call_id),'response':json.loads(payload)})+'\n')
        db.close()
        print(f'Completed {len(results)} records; estimated local USD {spent:.6f}')

def wilson(k,n):
    z=1.959963984540054; p=k/n; den=1+z*z/n; center=(p+z*z/(2*n))/den; h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return center-h,center+h

def analyze(args):
    from analysis import report
    report(Path(args.out))
def main():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError: pass
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='cmd',required=True)
    s=sub.add_parser('prepare'); s.add_argument('phase',choices=['pilot','final']); s.add_argument('--fixture',action='store_true'); s.add_argument('--pilot',default='pilot_manifest.json'); s.add_argument('--output',required=True); s.add_argument('--mmlu-revision'); s.add_argument('--gsm-revision')
    s=sub.add_parser('run'); s.add_argument('--manifest',required=True); s.add_argument('--out',required=True); s.add_argument('--live',action='store_true'); s.add_argument('--cap',type=float,required=True); s.add_argument('--timeout',type=float,default=90); s.add_argument('--retries',type=int,default=4); s.add_argument('--max-tokens',type=int,default=DEFAULT_MAX_TOKENS)
    s=sub.add_parser('analyze'); s.add_argument('--out',required=True)
    a=p.parse_args();
    {'prepare':prepare,'run':run,'analyze':analyze}[a.cmd](a)
if __name__=='__main__': main()
