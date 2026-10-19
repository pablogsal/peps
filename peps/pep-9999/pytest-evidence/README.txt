pytest comparison evidence

All measurements use the same native-assert prototype executable. They do
not measure ordinary-mode overhead relative to unmodified CPython.

Inputs:
- SymPy 1.14.0 from ../workload-evidence/vendor/sympy.
- pytest commit 420cf37a3fc8c03c9a4769c2635a03773d27be10.
- Dependency versions in requirements.txt and hashes in source-manifest.json.
- Hypothesis 6.140.3 is a pure-Python dependency required by SymPy conftest.

Reproduction layout:
1. Restore the workload-evidence vendor directory with its requirements.txt.
2. Keep the supplied pytest-src, dependencies, and hypothesis-deps directories.
   They contain the measured Python source and package license files.
3. Use the prototype interpreter without -X assert_details:

   ./python /path/to/pytest-evidence/compare_compile.py
   ./python /path/to/pytest-evidence/compare_runtime.py
   python3 /path/to/pytest-evidence/check_measurements.py

The archive supplies pytest and its benchmark dependencies. requirements.txt
and hypothesis-packages.json identify the dependency versions. The separate
workload-evidence/packages.json identifies the SymPy wheel and its hash.
The verification script checks the original recorded environment. A new run
on another build needs its own executable hash and source records.

Compilation measures source bytes already in memory. The pytest mode
includes ast.parse, rewrite_asserts, and compile. Capture compiles bytes
with ast.PyCF_ASSERT_DETAILS. Ordinary mode compiles bytes with flags=0.
All modes use optimize=0 and dont_inherit=True. Bytecode totals include
nested code objects and caches. Marshal totals exclude .pyc headers.
All six mode permutations follow a complete untimed pass in each mode.
No imports, file access, serialization, or test execution occur in this timer.

Runtime executes four unchanged files from sympy/core/tests: test_basic.py,
test_sympify.py, test_symbol.py, and test_expr.py. It retains the SymPy
conftest and uses the same pytest runner, empty configuration, and options.
The native adapter replaces pytest's private _rewrite_test function, so
pytest still selects the same modules. This is a benchmark adapter, not
upstream pytest support. Production library imports retain ordinary asserts.
No assertion callbacks are installed. The prototype traceback formatter
supplies capture explanations to pytest, as verify_reporting.json confirms. The selected tests include four
expected failures and their reports. This does not isolate failure-report
performance.

Each observation uses a fresh process, a fixed hash seed, no third-party
plugin autoload, and a fresh empty bytecode-cache prefix. -B prevents cache
writes. The host filesystem cache is warm after the pilot. Parent wall time
includes interpreter startup through shutdown. The test-loop timer excludes collection, including test-module compilation.
It includes fixtures, imports during tests, and reports. Each run
checks generated local names, collected node IDs, and every test outcome.

The parent pins each run to one allowed logical CPU. Affinity does not
reserve that CPU. The shared host prevents claims about small differences
or other workloads. Raw observations, run commands, source hashes, build
identity, CPU numbers, and UTC times remain in the JSON files.

setup-rejected contains a CPython 3.14 Hypothesis wheel that cannot import
under this CPython 3.16 prototype. No measurement uses that wheel.
It is excluded from the evidence archive.
