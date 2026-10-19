"""Compare plain compile, pytest rewrite, and native capture on identical tests."""
import ast
import datetime
import hashlib
import itertools
import json
import marshal
import os
from pathlib import Path
import random
import statistics
import sys
import sysconfig
import time
import types

ROOT=Path(__file__).resolve().parent
EVIDENCE=ROOT.parent/'workload-evidence'
sys.path[:0]=[str(ROOT/'pytest-src'),str(ROOT/'dependencies'),str(EVIDENCE)]
from _pytest.assertion.rewrite import rewrite_asserts
from measure_workloads import choose_cpu


def compile_mode(source, filename, mode):
    if mode=='pytest':
        tree=ast.parse(source,filename)
        rewrite_asserts(tree,source,filename)
        return compile(tree,filename,'exec',dont_inherit=True,optimize=0)
    flags=ast.PyCF_ASSERT_DETAILS if mode=='capture' else 0
    return compile(source,filename,'exec',flags=flags,dont_inherit=True,optimize=0)


def bytecode_size(code):
    return len(code.co_code)+sum(bytecode_size(c) for c in code.co_consts if isinstance(c,types.CodeType))


def main():
    if 'assert_details' in sys._xoptions:
        raise RuntimeError('Run without -X assert_details; modes use explicit flags')
    cpu=choose_cpu()
    previous=json.loads((EVIDENCE/'test-corpus.json').read_text())
    sources=[]
    for row in previous['rows']:
        source=(Path(previous['root'])/row['path']).read_bytes()
        if hashlib.sha256(source).hexdigest()!=row['sha256']:
            raise RuntimeError('Source changed: '+row['path'])
        sources.append((row['path'],source))
    modes=['plain','pytest','capture']
    result=dict(start_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                executable=sys.executable,executable_sha256=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
                version=sys.version,configure=sysconfig.get_config_var('CONFIG_ARGS'),
                cflags=sysconfig.get_config_var('PY_CFLAGS'),cpu=cpu,load_start=os.getloadavg(),
                harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                pytest_commit=json.loads((ROOT/'source-manifest.json').read_text())['pytest_commit'],
                input_manifest_sha256=hashlib.sha256((EVIDENCE/'test-corpus.json').read_bytes()).hexdigest(),
                files=len(sources),assertions=previous['assertions'],rows=[],blocks=[],
                method='All source bytes in memory. Plain and capture compile bytes directly. pytest parses, rewrites, and compiles. optimize=0, dont_inherit=True. No imports, IO, serialization, or test execution inside the timer. All six mode permutations; one complete untimed pass per mode before timing.')
    aggregate={mode:dict(bytecode_bytes=0,marshal_bytes=0) for mode in modes}
    for filename,source in sources:
        row={'path':filename,'sha256':hashlib.sha256(source).hexdigest(),'modes':{}}
        for mode in modes:
            code=compile_mode(source,filename,mode)
            sizes={'bytecode_bytes':bytecode_size(code),'marshal_bytes':len(marshal.dumps(code))}
            row['modes'][mode]=sizes
            for key,value in sizes.items():aggregate[mode][key]+=value
        result['rows'].append(row)
    result['totals']=aggregate
    orders=list(itertools.permutations(modes))
    random.Random(20261018).shuffle(orders)
    for i,order in enumerate(orders):
        block={'order':order,'seconds':{}}
        for mode in order:
            start=time.perf_counter()
            for filename,source in sources:
                compile_mode(source,filename,mode)
            block['seconds'][mode]=time.perf_counter()-start
        result['blocks'].append(block)
        (ROOT/'compile.json').write_text(json.dumps(result,indent=2)+'\n')
        print(f'Compilation block {i+1}/6: '+json.dumps(block['seconds']),flush=True)
    result['median_seconds']={m:statistics.median(b['seconds'][m] for b in result['blocks']) for m in modes}
    result['end_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    result['load_end']=os.getloadavg()
    (ROOT/'compile.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'median_seconds':result['median_seconds'],'totals':result['totals']},indent=2),flush=True)


if __name__=='__main__':main()
