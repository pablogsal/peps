"""Measure three pyperformance workloads with assertion capture off and on."""
import argparse
import datetime
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys
import sysconfig
import time

ROOT = Path(__file__).resolve().parent
PYTHON = Path('/home/pablogsal/github/cpython/native-assert-prototype-20261018/python')


def upstream(name):
    path = ROOT / 'upstream' / name / 'run_benchmark.py'
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def workload(name):
    sys.path.insert(0, str(ROOT / 'vendor'))
    if name == 'django_template':
        import django
        import django.conf
        django.conf.settings.configure(TEMPLATES=[{
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
        }])
        django.setup()
        module = upstream('bm_django_template')

        class FunctionCapture:
            def bench_func(self, name, function, *args):
                self.function = lambda: function(*args)

        runner = FunctionCapture()
        module.bench_django_template(runner, 100)
        return runner.function, lambda: None, lambda value: hashlib.sha256(value.encode()).hexdigest(), 5
    if name == 'html5lib':
        import html5lib
        from xml.etree import ElementTree
        data = (ROOT / 'upstream/bm_html5lib/data/w3_tr_html5.html').read_bytes()
        html_file = io.BytesIO(data)

        def parse():
            html_file.seek(0)
            return html5lib.parse(html_file)

        return parse, lambda: None, lambda value: hashlib.sha256(ElementTree.tostring(value)).hexdigest(), 3
    if name == 'sympy_expand':
        import gc
        import sympy
        from sympy.core.cache import clear_cache
        gc.disable()  # Match the upstream SymPy benchmark.

        def expand():
            x, y, z = sympy.symbols('x y z')
            return sympy.expand((1 + x + y + z) ** 20)

        return expand, clear_cache, lambda value: hashlib.sha256(str(value).encode()).hexdigest(), 1
    raise ValueError(name)


def worker(name, samples):
    function, before, digest, loops = workload(name)
    for _ in range(2):
        before()
        result = function()
    fingerprint = digest(result)
    times = []
    for _ in range(samples):
        elapsed = 0
        for _ in range(loops):
            before()
            start = time.perf_counter_ns()
            result = function()
            elapsed += time.perf_counter_ns() - start
        times.append(elapsed / loops / 1e9)
    if digest(result) != fingerprint:
        raise RuntimeError('Workload output changed')
    # Verify the CLI mode after timing. No handler runs in the benchmark.
    import assertionlib
    try:
        exec(compile('assert 1 == 2', '<mode probe>', 'exec'))
    except AssertionError as error:
        captured = assertionlib.get_details(error) is not None
    expected = 'assert_details' in sys._xoptions
    if captured != expected:
        raise RuntimeError('Incorrect capture mode')
    print(json.dumps(dict(name=name, capture=captured, samples_seconds=times,
                          loops=loops, warmups=2, digest=fingerprint,
                          affinity=sorted(os.sched_getaffinity(0)),
                          load=os.getloadavg())))


def choose_cpu():
    def stat():
        rows = {}
        for line in Path('/proc/stat').read_text().splitlines():
            words = line.split()
            if words[0].startswith('cpu') and words[0][3:].isdigit():
                values = list(map(int, words[1:9]))
                rows[int(words[0][3:])] = sum(values), values[3] + values[4]
        return rows
    first = stat()
    time.sleep(0.5)
    second = stat()
    def busy(cpu):
        total = second[cpu][0] - first[cpu][0]
        idle = second[cpu][1] - first[cpu][1]
        return (total - idle) / max(total, 1)
    cpu = min(os.sched_getaffinity(0), key=busy)
    os.sched_setaffinity(0, {cpu})
    return cpu


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', choices=['django_template', 'html5lib', 'sympy_expand'])
    parser.add_argument('--pairs', type=int, default=10)
    parser.add_argument('--samples', type=int, default=5)
    parser.add_argument('--output', type=Path, default=ROOT / 'runtime.json')
    args = parser.parse_args()
    if args.worker:
        worker(args.worker, args.samples)
        return
    cpu = choose_cpu()
    result = dict(start_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  python=str(PYTHON), python_sha256=hashlib.sha256(PYTHON.read_bytes()).hexdigest(),
                  harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  version=sys.version, configure=sysconfig.get_config_var('CONFIG_ARGS'),
                  cflags=sysconfig.get_config_var('PY_CFLAGS'), cpu=cpu,
                  platform=sysconfig.get_platform(), load_start=os.getloadavg(),
                  cpuinfo=Path('/proc/cpuinfo').read_text().split('\n\n')[0],
                  method='Fresh processes; median of process medians. Paired modes alternate. Imports, compilation and digest checks excluded. GC disabled only for SymPy, as upstream.',
                  samples_per_process=args.samples, pairs=args.pairs,
                  workloads={})
    rng = random.Random(20261018)
    for name in ('django_template', 'html5lib', 'sympy_expand'):
        pairs = []
        for pair in range(args.pairs):
            order = ['plain', 'capture'] if pair % 2 == 0 else ['capture', 'plain']
            values = {'order': order, 'modes': {}}
            for mode in order:
                cmd = [str(PYTHON), '-S', '-B', '-X',
                       f'pycache_prefix={ROOT / "empty-cache" / mode}']
                if mode == 'capture':
                    cmd += ['-X', 'assert_details']
                cmd += [str(Path(__file__).resolve()), '--worker', name,
                        '--samples', str(args.samples)]
                env = os.environ.copy()
                env['PYTHONHASHSEED'] = '0'
                env.pop('PYTHONPATH', None)
                env.pop('PYTHONHOME', None)
                completed = subprocess.run(cmd, text=True, capture_output=True, env=env)
                if completed.returncode:
                    raise RuntimeError(completed.stderr)
                row = json.loads(completed.stdout)
                row['command'] = cmd
                values['modes'][mode] = row
            if values['modes']['plain']['digest'] != values['modes']['capture']['digest']:
                raise RuntimeError('Capture changed the output')
            pairs.append(values)
            print(f'{name}: pair {pair+1}/{args.pairs}', flush=True)
        medians = {mode: [statistics.median(p['modes'][mode]['samples_seconds']) for p in pairs]
                   for mode in ('plain', 'capture')}
        ratios = [b / a for a, b in zip(medians['plain'], medians['capture'])]
        row = dict(pairs=pairs, process_medians=medians,
                   median_seconds={mode: statistics.median(vals) for mode, vals in medians.items()},
                   paired_ratios=ratios,
                   paired_ratio_range=[min(ratios), max(ratios)])
        row['ratio'] = row['median_seconds']['capture'] / row['median_seconds']['plain']
        # Paired bootstrap uses processes as units, not individual inner values.
        estimates = []
        for _ in range(10000):
            indices = [rng.randrange(len(pairs)) for _ in pairs]
            estimates.append(statistics.median([medians['capture'][i] for i in indices]) /
                             statistics.median([medians['plain'][i] for i in indices]))
        estimates.sort()
        row['bootstrap_ratio_95'] = [estimates[249], estimates[9749]]
        result['workloads'][name] = row
        args.output.write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps({k:v for k,v in row.items() if k not in ('pairs','process_medians','paired_ratios')}), flush=True)
    result['end_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result['load_end'] = os.getloadavg()
    args.output.write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
