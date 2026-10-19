"""Compile all non-test Python modules in four pinned source corpora."""
import ast
import datetime
import hashlib
import json
import marshal
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
import types

from measure_workloads import choose_cpu

ROOT = Path(__file__).resolve().parent
REPO = Path('/home/pablogsal/github/cpython/native-assert-prototype-20261018')
MODES = {'plain': 0, 'capture': ast.PyCF_ASSERT_DETAILS}


def totals(code):
    values = dict(code_objects=1, bytecode_bytes=len(code.co_code),
                  location_table_bytes=len(code.co_linetable),
                  exception_table_bytes=len(code.co_exceptiontable),
                  local_slots=code.co_nlocals)
    for value in code.co_consts:
        if isinstance(value, types.CodeType):
            for key, count in totals(value).items():
                values[key] += count
    return values


def excluded(path):
    return (any(p.startswith('test') or p.endswith('_test') or p == 'benchmarks'
                for p in path.parts[:-1]) or path.name.startswith('test_'))


def measure(name, root, paths):
    sources = []
    skips = []
    rows = []
    aggregate = {mode: {} for mode in MODES}
    for path in sorted(paths):
        relative = path.relative_to(root)
        if excluded(relative):
            skips.append({'path': str(relative), 'reason': 'test or benchmark source'})
            continue
        source = path.read_bytes()
        filename = str(relative)
        # AST counts are separate from the timed compilations.
        tree = ast.parse(source, filename)
        assertions = sum(isinstance(n, ast.Assert) for n in ast.walk(tree))
        row = dict(path=filename, source_bytes=len(source), assertions=assertions,
                   sha256=hashlib.sha256(source).hexdigest(), modes={})
        for mode, flags in MODES.items():
            code = compile(source, filename, 'exec', flags=flags,
                           dont_inherit=True, optimize=0)
            sizes = totals(code)
            sizes['marshal_bytes'] = len(marshal.dumps(code))
            row['modes'][mode] = sizes
            for key, count in sizes.items():
                aggregate[mode][key] = aggregate[mode].get(key, 0) + count
        sources.append((filename, source))
        rows.append(row)
    # First compile all sources in both modes before the timed repetitions.
    # Measurement above supplies this warmup and all input is already in memory.
    trials = []
    for trial in range(10):
        modes = list(MODES) if trial % 2 == 0 else list(reversed(MODES))
        values = {'order': modes, 'seconds': {}}
        for mode in modes:
            start = time.perf_counter()
            for filename, source in sources:
                compile(source, filename, 'exec', flags=MODES[mode],
                        dont_inherit=True, optimize=0)
            values['seconds'][mode] = time.perf_counter() - start
        trials.append(values)
        print(f'{name}: pair {trial+1}/10', flush=True)
    medians = {mode: statistics.median(t['seconds'][mode] for t in trials) for mode in MODES}
    return dict(root=str(root), files=len(rows),
                files_with_assertions=sum(row['assertions'] > 0 for row in rows),
                assertions=sum(row['assertions'] for row in rows),
                source_bytes=sum(row['source_bytes'] for row in rows),
                totals=aggregate, compile_trials=trials,
                compile_median_seconds=medians,
                compile_ratio=medians['capture'] / medians['plain'],
                rows=rows, excluded=skips)


def main():
    cpu = choose_cpu()
    result = dict(start_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  version=sys.version, cpu=cpu, load_start=os.getloadavg(),
                  harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  cpython_base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
                  exclusions='Directory components that start with test, end with _test, or equal benchmarks; filenames that start with test_. Only .py files. No selection on assertion count.',
                  compile_scope='Source bytes already in memory. optimize=0. Ten alternating pairs after warmup. No imports, file IO, or marshal in the timed region.',
                  corpora={})
    names = subprocess.check_output(['git','ls-files','Lib'],cwd=REPO,text=True).splitlines()
    paths = [REPO / name for name in names if name.endswith('.py')]
    specs = [('stdlib', REPO / 'Lib', paths)]
    for name in ('django','html5lib','sympy'):
        root = ROOT / 'vendor' / name
        specs.append((name, root, list(root.rglob('*.py'))))
    for name, root, paths in specs:
        result['corpora'][name] = measure(name, root, paths)
        (ROOT / 'corpora.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({key:value for key,value in result['corpora'][name].items()
                          if key not in ('rows','excluded','compile_trials')}),flush=True)
    result['end_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result['load_end'] = os.getloadavg()
    (ROOT / 'corpora.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__ == '__main__':
    main()
