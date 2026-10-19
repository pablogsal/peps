"""Compile the test_*.py files under SymPy tests directories."""
import ast
import datetime
import hashlib
import json
import marshal
import os
from pathlib import Path
import statistics
import sys
import time

from measure_corpora import totals
from measure_workloads import choose_cpu

ROOT=Path(__file__).resolve().parent
root=ROOT/'vendor/sympy'
cpu=choose_cpu()
result=dict(start_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            version=sys.version, cpu=cpu, load_start=os.getloadavg(),
            harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            helper_sha256=hashlib.sha256((ROOT/'measure_corpora.py').read_bytes()).hexdigest(),
            selection='test_*.py under a directory component exactly named tests in SymPy 1.14.0; all selected files compile in both modes.',
            root=str(root), rows=[], compile_trials=[])
sources=[]
aggregate={mode:{} for mode in ('plain','capture')}
modes={'plain':0,'capture':ast.PyCF_ASSERT_DETAILS}
paths=sorted(p for p in root.rglob('test_*.py') if 'tests' in p.relative_to(root).parts[:-1])
for path in paths:
    filename=str(path.relative_to(root))
    source=path.read_bytes()
    tree=ast.parse(source, filename)
    row=dict(path=filename,source_bytes=len(source),
             assertions=sum(isinstance(n,ast.Assert) for n in ast.walk(tree)),
             sha256=hashlib.sha256(source).hexdigest(),modes={})
    for mode,flags in modes.items():
        code=compile(source,filename,'exec',flags=flags,dont_inherit=True,optimize=0)
        sizes=totals(code)
        sizes['marshal_bytes']=len(marshal.dumps(code))
        row['modes'][mode]=sizes
        for key,value in sizes.items():
            aggregate[mode][key]=aggregate[mode].get(key,0)+value
    sources.append((filename,source))
    result['rows'].append(row)
for trial in range(10):
    order=list(modes) if trial % 2 == 0 else list(reversed(modes))
    sample={'order':order,'seconds':{}}
    for mode in order:
        start=time.perf_counter()
        for filename,source in sources:
            compile(source,filename,'exec',flags=modes[mode],dont_inherit=True,optimize=0)
        sample['seconds'][mode]=time.perf_counter()-start
    result['compile_trials'].append(sample)
    print(f'SymPy tests: pair {trial+1}/10',flush=True)
result.update(files=len(paths),assertions=sum(r['assertions'] for r in result['rows']),
              totals=aggregate,
              compile_median_seconds={mode:statistics.median(r['seconds'][mode] for r in result['compile_trials']) for mode in modes},
              end_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),load_end=os.getloadavg())
(ROOT/'test-corpus.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('rows','compile_trials')},indent=2))
