"""Run selected, unchanged SymPy tests with three assertion implementations."""
import argparse
import datetime
import hashlib
import itertools
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT.parent / 'workload-evidence'
SYMPY = EVIDENCE / 'vendor/sympy'
FILES = ['test_basic.py', 'test_sympify.py', 'test_symbol.py', 'test_expr.py']
PATHS = [SYMPY / 'core/tests' / name for name in FILES]
sys.path[:0] = [str(ROOT / 'pytest-src'), str(ROOT / 'hypothesis-deps'),
               str(ROOT / 'dependencies'), str(EVIDENCE / 'vendor')]


def worker(mode, output):
    import ast
    import importlib.util
    import inspect
    import types
    import pytest
    from _pytest.assertion import rewrite

    if 'assert_details' in sys._xoptions:
        raise RuntimeError('Do not enable global assertion capture')
    compiled = []
    original = rewrite._rewrite_test

    def rewrite_test(path, config):
        if mode == 'capture':
            source = path.read_bytes()
            code = compile(source, str(path), 'exec',
                           flags=ast.PyCF_ASSERT_DETAILS,
                           dont_inherit=True, optimize=0)
            result = importlib.util.source_hash(source), code
        else:
            result = original(path, config)
        compiled.append(str(path))
        return result

    rewrite._rewrite_test = rewrite_test
    result = {'mode': mode, 'compiled': compiled, 'reports': [],
              'nodeids': [], 'code_checks': {}, 'cpu': sorted(os.sched_getaffinity(0))}

    def variables(code):
        names = set(code.co_varnames)
        for value in code.co_consts:
            if isinstance(value, types.CodeType):
                names.update(variables(value))
        return names

    class Recorder:
        def pytest_collection_finish(self, session):
            result['nodeids'] = [item.nodeid for item in session.items]
            for path in PATHS:
                modules = [item.module for item in session.items
                           if Path(item.module.__file__).resolve() == path.resolve()]
                if not modules:
                    raise RuntimeError(f'No tests from {path}')
                names = set()
                for name, value in vars(modules[0]).items():
                    if name.startswith('test_') and inspect.isfunction(value):
                        names.update(variables(inspect.unwrap(value).__code__))
                native = any(name.startswith('.assertion.') for name in names)
                rewritten = any(name.startswith('@py_assert') for name in names)
                if (native, rewritten) != (mode == 'capture', mode == 'pytest'):
                    raise RuntimeError(f'Wrong assertion code for {path}: {native}, {rewritten}')
                result['code_checks'][path.name] = {'capture': native, 'pytest': rewritten}

        @pytest.hookimpl(wrapper=True)
        def pytest_runtestloop(self, session):
            start = time.perf_counter()
            try:
                return (yield)
            finally:
                result['test_loop_seconds'] = time.perf_counter() - start

        def pytest_runtest_logreport(self, report):
            result['reports'].append({'nodeid': report.nodeid, 'when': report.when,
                                      'outcome': report.outcome,
                                      'wasxfail': str(getattr(report, 'wasxfail', ''))})

    args = ['-q', '-p', 'no:cacheprovider', '-c', str(ROOT / 'pytest.ini'),
            '--rootdir', str(SYMPY), '--confcutdir', str(SYMPY),
            '--assert=plain' if mode == 'plain' else '--assert=rewrite']
    args.extend(str(path) for path in PATHS)
    start = time.perf_counter()
    result['exit_code'] = int(pytest.main(args, plugins=[Recorder()]))
    result['pytest_main_seconds'] = time.perf_counter() - start
    result['pytest_args'] = args
    Path(output).write_text(json.dumps(result, indent=2) + '\n')
    return result['exit_code']


def main(pilot):
    sys.path.insert(0, str(EVIDENCE))
    from measure_workloads import choose_cpu
    cpu = choose_cpu()
    modes = ['plain', 'pytest', 'capture']
    orders = [tuple(modes)] if pilot else list(itertools.permutations(modes))
    random.Random(20261018).shuffle(orders)
    result = {'start_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'cpu': cpu, 'load_start': os.getloadavg(), 'version': sys.version,
              'executable': sys.executable,
              'executable_sha256': hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
              'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'pytest_commit': json.loads((ROOT / 'source-manifest.json').read_text())['pytest_commit'],
              'inputs': {str(p.relative_to(SYMPY)): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in PATHS}, 'blocks': [],
              'method': 'Fresh process per observation, no .pyc reads or writes, warm OS cache. '
                        'All six mode permutations. Same pytest runner and conftest. '
                        'Capture replaces only the pytest rewrite compilation hook. '
                        'Third-party plugin autoload disabled. No capture callbacks. '
                        'Parent wall time includes startup, imports, collection, compilation, '
                        'test execution and shutdown. Test-loop timer includes fixtures and reports.'}
    destination = ROOT / ('runtime-pilot' if pilot else 'runtime-runs')
    destination.mkdir(exist_ok=True)
    reference = None
    for block_index, order in enumerate(orders):
        block = {'order': order, 'runs': {}}
        for mode in order:
            stem = destination / f'{block_index + 1:02}-{mode}'
            env = {k: v for k, v in os.environ.items() if not k.startswith('PYTHON')}
            env.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTHONHASHSEED='0',
                       PYTHONNOUSERSITE='1', SYMPY_GROUND_TYPES='python')
            with tempfile.TemporaryDirectory(prefix='assert-compare-') as cache:
                command = [sys.executable, '-S', '-B', '-X', f'pycache_prefix={cache}',
                           str(Path(__file__).resolve()), '--worker', mode,
                           '--output', str(stem.with_suffix('.json'))]
                start = time.perf_counter()
                completed = subprocess.run(command, env=env, cwd=ROOT,
                                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                           text=True)
                elapsed = time.perf_counter() - start
            stem.with_suffix('.log').write_text(completed.stdout)
            if completed.returncode:
                raise RuntimeError(f'{mode} exited {completed.returncode}: {stem}.log')
            row = json.loads(stem.with_suffix('.json').read_text())
            row['command_seconds'] = elapsed
            row['command'] = command
            signature = {'nodeids': row['nodeids'], 'reports': row['reports']}
            if reference is None:
                reference = signature
            elif signature != reference:
                raise RuntimeError(f'Test selection or outcomes differ in {stem}')
            block['runs'][mode] = row
            print(f'Block {block_index + 1}/{len(orders)} {mode}: '
                  f'command {elapsed:.3f}s, test loop {row["test_loop_seconds"]:.3f}s',
                  flush=True)
        result['blocks'].append(block)
        (ROOT / ('runtime-pilot.json' if pilot else 'runtime.json')).write_text(
            json.dumps(result, indent=2) + '\n')
    result['medians'] = {
        mode: {key: statistics.median(block['runs'][mode][key] for block in result['blocks'])
               for key in ('command_seconds', 'pytest_main_seconds', 'test_loop_seconds')}
        for mode in modes}
    result['end_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result['load_end'] = os.getloadavg()
    (ROOT / ('runtime-pilot.json' if pilot else 'runtime.json')).write_text(
        json.dumps(result, indent=2) + '\n')
    print(json.dumps(result['medians'], indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', choices=['plain', 'pytest', 'capture'])
    parser.add_argument('--output')
    parser.add_argument('--pilot', action='store_true')
    args = parser.parse_args()
    if args.worker:
        sys.exit(worker(args.worker, args.output))
    main(args.pilot)
