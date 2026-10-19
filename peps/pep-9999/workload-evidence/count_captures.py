"""Count executed assertions outside the timed runs, using capture stores."""
from collections import Counter
import dis
import hashlib
import json
from pathlib import Path
import sys

from measure_workloads import workload

if not sys._xoptions.get('assert_details'):
    raise RuntimeError('Run this counter with -X assert_details')
name = sys.argv[1]
function, before, digest, loops = workload(name)
for _ in range(2):
    before()
    function()

monitor = sys.monitoring
tool = monitor.PROFILER_ID
monitor.use_tool_id(tool, 'assertion-count')
locations = {}
counts = Counter()


def start(code, offset):
    if '.assertion.0' in code.co_varnames:
        slots = {i.offset: i.positions.lineno for i in dis.get_instructions(code)
                 if i.opname in ('STORE_FAST_BORROW', 'COPY_TO_FAST')
                 and i.argval == '.assertion.0'}
        if not slots:
            raise RuntimeError('No first capture store for ' + code.co_qualname)
        locations[code] = slots
        monitor.set_local_events(tool, code, monitor.events.INSTRUCTION)
    return monitor.DISABLE


def instruction(code, offset):
    if offset in locations[code]:
        counts[(code.co_filename, code.co_qualname, locations[code][offset])] += 1


monitor.register_callback(tool, monitor.events.PY_START, start)
monitor.register_callback(tool, monitor.events.INSTRUCTION, instruction)
records = []
for _ in range(2):
    before()
    counts.clear()
    for code in locations:
        monitor.set_local_events(tool, code, monitor.events.INSTRUCTION)
    monitor.set_events(tool, monitor.events.PY_START)
    value = function()
    monitor.set_events(tool, 0)
    for code in locations:
        monitor.set_local_events(tool, code, 0)
    records.append(dict(count=sum(counts.values()), digest=digest(value),
                        locations=[dict(file=f, function=fn, line=line, count=count)
                                   for (f, fn, line), count in sorted(counts.items())]))
for code in locations:
    monitor.set_local_events(tool, code, 0)
monitor.free_tool_id(tool)
if records[0]['count'] != records[1]['count']:
    raise RuntimeError('Count varies between calls')
print(json.dumps(dict(workload=name, records=records,
                     capture_enabled=sys._xoptions.get('assert_details'),
                     capture_code_objects_seen=len(locations),
                     executable=sys.executable, version=sys.version,
                     executable_sha256=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
                     workload_harness_sha256=hashlib.sha256(Path(__file__).with_name('measure_workloads.py').read_bytes()).hexdigest(),
                     method='Count STORE_FAST_BORROW or COPY_TO_FAST to .assertion.0. Each executed captured assertion writes its first slot once. Two warmups; then two untimed calls. Counts include imported source modules.',
                     script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2))
