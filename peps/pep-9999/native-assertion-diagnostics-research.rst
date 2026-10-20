:orphan:

Assertion diagnostics: research notes
=====================================

Research date: 19 October 2026. These notes accompany the shorter PEP.
Public sources establish prior work and existing contracts. Local records
support the prototype measurements. The proposal remains a draft.

The API revision on 20 October 2026 introduces ``error.details``,
``details.format()``, and ``assertionlib.formatter()``. The records below
retain their original source revisions and APIs. This API revision does
not change compiler capture or the bytecode in the measured workloads.

Public evidence
---------------

* `CPython issue 26702 <https://bugs.python.org/issue26702>`_, 6 April 2016.
  Barry Warsaw describes a failure whose missing intermediate values
  required changes to installed code. This supports the concrete user
  problem in the motivation. It is not an evaluation of this design.

* `Native assertion discussion <https://discuss.python.org/t/97921>`_,
  July and August 2025. Participants discuss annotated assertions,
  short circuit evaluation, output quality, and overhead. The draft
  acknowledges the earlier plan and keeps capture optional. The thread's
  cost claims are opinions, not measurements of this prototype.

* `Python 3.11.0b3 report <https://discuss.python.org/t/16175>`_, 1 June 2022.
  The release manager records a pytest compatibility failure after stricter
  AST validation. This supports the maintenance argument. It does not
  establish that native capture prevents every future compatibility bug.

* `pytest assertion documentation
  <https://docs.pytest.org/en/stable/how-to/assert.html>`_. This describes
  subexpression explanations, import-time rewriting, and helper registration.
  It supports the proposed separation between module selection and capture.

* `unittest assertion documentation
  <https://docs.python.org/3/library/unittest.html#unittest.TestCase.assertEqual>`_
  describes type-specific differences for ``TestCase.assertEqual``.
  The comparison table distinguishes these reports from subexpression
  capture in the compiler.

* `Pinned pytest source
  <https://github.com/pytest-dev/pytest/blob/420cf37a3fc8c03c9a4769c2635a03773d27be10/src/_pytest/assertion/rewrite.py>`_.
  This is the revision used by the local experiment. ``_rewrite_test``
  parses, rewrites, and compiles source. ``visit_Assert`` constructs the
  replacement statements.

* `PEP 657 <https://peps.python.org/pep-0657/>`_ specifies source positions.
  `PEP 678 <https://peps.python.org/pep-0678/#non-goals>`_ excludes structured
  data from the purpose of exception notes. These facilities do not supply
  the operand objects that this proposal exposes.

* The `assert reference
  <https://docs.python.org/3/reference/simple_stmts.html#the-assert-statement>`_
  defines assertion removal under optimization. This proposal preserves
  that rule. `PEP 488 <https://peps.python.org/pep-0488/>`_ describes the
  optimization suffix for cache filenames.

* The `intrinsic instruction reference
  <https://docs.python.org/3/library/dis.html#opcode-CALL_INTRINSIC_2>`_
  confirms that ``CALL_INTRINSIC_2`` already exists. The `import C API
  <https://docs.python.org/3/c-api/import.html#c.PyImport_GetModule>`_
  confirms that ``PyImport_GetModule`` obtains an already imported module.
  The private capture layout and dispatcher behavior come from the local
  prototype, not from these references.

* `Context variables <https://docs.python.org/3/library/contextvars.html>`_
  provide the scope mechanism. `PEP 669 <https://peps.python.org/pep-0669/>`_
  defines an alternative event system. The decision to use context-local
  handlers is a proposal choice, not a requirement of either source.

* `AssertionLib on PyPI <https://pypi.org/project/AssertionLib/>`_ confirms
  the module-name conflict. The draft leaves the final name open.

Simplification measurements, 20 October 2026
--------------------------------------------

The current PEP uses the simplified prototype at commit
``d944fbc4015388d800d872614bc9c4ab565897a0``. It uses existing store, load,
and cleanup instructions. It removes success callbacks, assertion retention
under optimization, and duplicate capture metadata.

The compilation experiment uses the same 612 SymPy 1.14.0 test files and
pinned pytest revision as the earlier experiment. Six runs cover all mode
orders. Median compile times are 1.26 seconds for ordinary assertions,
48.20 seconds for pytest, and 9.64 seconds for capture.

Capture produces 25.90 MiB of bytecode and 95.48 MiB of serialized code.
The earlier prototype produced 20.71 MiB and 116.22 MiB, respectively.
Thus the simpler implementation adds 25% more bytecode and removes 18% of
the serialized size. The capture plan still includes expression values,
truth results, source locations, and comparison links.

Across the same eleven assertion-loop cases, the geometric mean time is
1.86x ordinary assertions for capture and 1.65x for pytest. These runs use
one executable, CPU 17, nine samples per case, and shuffled mode order.
The earlier and current prototypes have similar loop cost in these samples.
The shared host prevents a stable claim about their small runtime difference.

Current records:

* :download:`Compilation samples and sizes <simplification-evidence/compile.json>`
* :download:`Loop and failure latency samples <simplification-evidence/loops.json>`
* :download:`Comparison of simplification rounds <simplification-evidence/summary.json>`
* :download:`Benchmark script <simplification-evidence/benchmark.py>` and
  :download:`compilation reproduction script <simplification-evidence/reproduce_compile.py>`
* :download:`Method and reproduction instructions <simplification-evidence/README.txt>`
* :download:`Artifact hashes <simplification-evidence/manifest.json>`

The records below describe the earlier prototype, before these changes.
They retain the earlier real-library execution runs and source manifests.
The current implementation has no new end-to-end library runtime result.

Earlier measurement evidence
-----------------------------

These records contain measurements from 19 October 2026 UTC. The earlier
assertion-loop and formatter measurements remain in the technical notes.
The two performance plots are no longer part of the PEP.

.. list-table:: Current records
    :header-rows: 1
    :widths: 40 60

    * - Evidence
      - Record
    * - Ordinary assertions, pytest rewrite, and compiler capture
      - :download:`Compile samples and sizes <pytest-evidence/compile.json>`
    * - Four SymPy test modules through the same pytest runner
      - :download:`Execution samples <pytest-evidence/runtime.json>`
    * - Comparison arithmetic, code modes, and test outcomes
      - :download:`Comparison checks <pytest-evidence/measurement-check.json>`
    * - Three workloads, 60 fresh processes
      - :download:`Runtime samples <workload-evidence/runtime.json>`
    * - Four library corpora, 2,411 Python files
      - :download:`File manifest and compile samples <workload-evidence/corpora.json>`
    * - SymPy test sources, 612 Python files
      - :download:`Test corpus <workload-evidence/test-corpus.json>`
    * - Executed assertions per operation
      - :download:`Counter script <workload-evidence/count_captures.py>` and
        :download:`counts <workload-evidence/capture-counts.json>`
    * - Recalculated medians, sizes, and source hashes
      - :download:`Measurement checks <workload-evidence/measurement-check.json>`
    * - Workload sources and input hashes
      - :download:`Pinned source manifest <workload-evidence/upstream-sources.json>`
    * - Package versions and wheel hashes
      - :download:`Install report <workload-evidence/packages.json>` and
        :download:`requirements <workload-evidence/requirements.txt>`

Comparison with pytest
~~~~~~~~~~~~~~~~~~~~~~

The comparison uses pytest commit
``420cf37a3fc8c03c9a4769c2635a03773d27be10`` and the same prototype
executable in all modes. It does not compare different interpreter builds.
The :download:`source manifest <pytest-evidence/source-manifest.json>` records the
pytest and dependency hashes. The :download:`reproduction notes <pytest-evidence/README.txt>` describe the directory layout and commands.

.. container:: table-block

    .. list-table:: Compilation of 612 SymPy test files
        :header-rows: 1
        :widths: 26 15 21 18 20
        :class: measurement-table

        * - Mode
          - Compile, s
          - Range, s
          - Bytecode, MiB
          - Serialized, MiB
        * - Ordinary asserts
          - 1.24
          - 1.22 to 1.71
          - 12.08
          - 20.57
        * - pytest rewrite
          - 48.57
          - 47.45 to 53.19
          - 89.33
          - 131.90
        * - Compiler capture
          - 14.10
          - 12.78 to 17.37
          - 20.71
          - 116.22

The compile experiment uses the same 612 SymPy test files as the earlier
two-mode experiment. It confirms every source hash before compilation.

Ordinary mode compiles source bytes with flags zero. Capture adds only
``ast.PyCF_ASSERT_DETAILS``. The pytest mode uses ``ast.parse()``,
``rewrite_asserts()``, and ``compile()``. All modes use ``optimize=0`` and
``dont_inherit=True``. The pytest pass hook is disabled.

The process reads all source bytes before the timer starts. An untimed
pass compiles every file in each mode and calculates code sizes. Six timed
blocks cover all permutations of the three modes in a fixed shuffled order.
Each block compiles every source file once per mode. The timer excludes
imports, file access, serialization, and test execution.

Bytecode totals
include nested code objects and inline caches. Marshal totals include
metadata and exclude cache headers and live memory.

.. container:: table-block

    .. list-table:: Selected SymPy tests: median and full range, seconds
        :header-rows: 1
        :widths: 24 17 22 17 20
        :class: measurement-table

        * - Mode
          - Command
          - Range
          - Test loop
          - Range
        * - Ordinary asserts
          - 7.88
          - 7.17 to 10.00
          - 5.64
          - 5.05 to 7.22
        * - pytest rewrite
          - 8.20
          - 7.85 to 11.36
          - 5.19
          - 5.08 to 7.23
        * - Compiler capture
          - 7.47
          - 7.31 to 10.14
          - 5.07
          - 5.05 to 7.07

The runtime experiment uses unchanged ``test_basic.py``, ``test_sympify.py``,
``test_symbol.py``, and ``test_expr.py`` from ``sympy/core/tests``.
It retains SymPy's conftest and selects these files before the pilot.
All modes use the same pytest runner, empty configuration, hash seed,
and pure-Python SymPy ground types. Third-party plugin autoload is disabled.
Hypothesis 6.140.3 supplies the dependency that SymPy's conftest requires.

Ordinary mode uses ``--assert=plain``. The other modes use pytest's module
selection hook. A benchmark adapter replaces its private ``_rewrite_test``
function for capture. The replacement compiles source bytes with
``ast.PyCF_ASSERT_DETAILS``. It returns the source hash and code object that
the hook expects. Production library imports retain ordinary assertions.

The adapter supplies no callback or report formatter. The prototype's
traceback formatter supplies capture explanations to pytest. A separate
:download:`failure-output check <pytest-evidence/verify_reporting.json>` confirms this
behavior for the invoice example in all three modes. The adapter is a
measurement tool, not upstream pytest support.

A pilot executes all three modes before the measured runs. Each of six
blocks uses fresh processes and a different mode order. Each process uses
``-S``, ``-B``, and an empty cache prefix, so no imports use cached bytecode.
The OS filesystem cache is warm.

The command timer includes interpreter
startup, imports, collection, compilation, test execution, and shutdown.
A hook around ``pytest_runtestloop`` measures fixtures, tests, and reports.
It includes imports that occur during tests. It excludes collection,
including test-module compilation. The same recorder runs in all modes.

The recorder checks hidden local names in the collected test functions.
Capture must contain ``.assertion.`` names. The pytest rewrite must contain
``@py_assert`` names. Ordinary mode must contain neither.

The recorder also compares
all collected node IDs and every setup, call, and teardown outcome.
The raw records retain these checks and each command's output. The check
script also confirms that both diagnostic modes compile exactly the four
test modules and their conftest. Ordinary mode uses no rewrite hook.

The :download:`compile harness <pytest-evidence/compare_compile.py>` and :download:`runtime harness <pytest-evidence/compare_runtime.py>` record their own hashes.
They also record the executable hash, pytest commit, CPU, and UTC times.
All results come from a shared host. CPU affinity does not reserve a core.
The PEP reports medians and the runtime ranges, without a significance claim.

All runs report 194 passed, 7 skipped, and 4 expected failures. The test-loop
timer includes expected failures and their reports. The results do not
estimate a complete SymPy suite or isolate failure-report cost. None of
these four modules uses Hypothesis test generators.

Within each block, capture minus pytest ranges from -3.82 to +0.67 seconds
for command time. For test-loop time, it ranges from -2.17 to -0.03 seconds.
The respective median differences are -0.57 and -0.05 seconds. These paired
values differ from subtraction of the separate mode medians. The record
retains all observations, including the large change in the second block.

The prototype uses a static interpreter build, with ``Py_ENABLE_SHARED=0``.
A :download:`serialization check <pytest-evidence/verify_serialization.json>` confirms
that a marshal round-trip preserves the invoice example's captured values
and formatted explanation. It uses the same executable as the benchmarks.

Library workloads
~~~~~~~~~~~~~~~~~

The workloads come from `pyperformance revision ccc0aeb
<https://github.com/python/pyperformance/tree/ccc0aeb7ad46d65b6dcd4160e0fdda4d885852dd/pyperformance/data-files/benchmarks>`_.
The local harness uses the Django benchmark's actual template and context.
It reproduces the HTML parser and SymPy expansion operations, with return
values retained for output checks. It does not run the pyperf command-line
runner. These are adapted workloads, not a full pyperformance result.

The selection preceded the timing run and covers three library tasks.
It does not claim statistical coverage of Python applications.

Django 5.2.8 renders a 100 by 100 table. html5lib 1.1 parses the upstream
133,837-byte HTML document from an in-memory byte stream. SymPy 1.14.0
expands ``(1 + x + y + z) ** 20``. As in the upstream benchmark, each
SymPy call starts with an empty SymPy cache, and cyclic GC is disabled.
Cache clearing is outside the timed region.

Both modes use the same prototype executable. The capture mode adds
``-X assert_details``. Each child uses ``-S``, ``-B``, a fixed hash seed,
and an empty, mode-specific bytecode-cache path. Imports compile source
before the timed region. Frozen modules keep their existing code.

The harness verifies capture mode with a failed assertion after timing.
There are no assertion handlers in the timed workloads.

A separate untimed run counts capture instructions with ``sys.monitoring``.
The first capture store writes ``.assertion.0`` once per executed assertion.
The counter follows those stores in every called Python function. It runs
the same workload after two warmups.

Each of two calls gives the same count:
zero for Django, 7,792 for html5lib, and 228 for SymPy. The counter is absent
from timed runs. Django measures only indirect effects after setup.
Its zero count does not estimate the cost of value capture.

.. container:: table-block

    .. list-table:: Time and captured assertions per operation
        :header-rows: 1
        :widths: 29 12 12 12 11 24
        :class: measurement-table

        * - Workload
          - Captured asserts
          - Ordinary, ms
          - Capture, ms
          - Change
          - 95% interval
        * - Django: 100 x 100 table
          - 0
          - 22.04
          - 22.16
          - +0.5%
          - -2.0% to +2.7%
        * - html5lib: parse 130.7 KiB
          - 7,792
          - 32.16
          - 32.69
          - +1.7%
          - -0.5% to +2.3%
        * - SymPy: polynomial expansion
          - 228
          - 219.60
          - 223.12
          - +1.6%
          - -1.3% to +5.3%


Each workload has ten pairs of fresh processes. The first mode alternates
between pairs. Each process executes two warmup calls and five timed
samples. A sample contains five Django calls, three HTML parser calls,
or one SymPy call. The record stores time per operation. The table uses
the median of the ten process medians for each mode.

The 95% intervals use 10,000 paired bootstrap resamples. Each resample
selects process pairs with replacement and recalculates the ratio of
medians. It does not treat the five samples within a process as independent
processes. Every interval includes zero change. The intervals cannot
account for unmeasured host interference or another machine's behavior.

The harness compares output hashes after warmup and after timed execution.
All 20 processes for each workload produce the same hash. Imports,
compilation, cache clearing, and output checks are outside the runtime
measurements. These results do not measure a complete application,
a complete test suite, or ordinary-mode overhead against unmodified CPython.

Earlier corpus measurements
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. container:: table-block

    .. list-table:: Additional code and compile time with capture
        :header-rows: 1
        :widths: 21 9 12 21 24 13
        :class: measurement-table

        * - Source corpus
          - Files
          - Asserts
          - Bytecode, KiB
          - Serialized, KiB
          - Compile time
        * - CPython ``Lib``
          - 702
          - 543
          - +28.5 (0.58%)
          - +270.5 (1.95%)
          - +0.9%
        * - Django 5.2.8
          - 875
          - 36
          - +2.0 (0.08%)
          - +21.3 (0.32%)
          - +0.2%
        * - html5lib 1.1
          - 33
          - 95
          - +5.1 (2.11%)
          - +46.3 (7.48%)
          - +7.4%
        * - SymPy 1.14.0
          - 801
          - 216
          - +11.0 (0.14%)
          - +117.5 (0.54%)
          - +0.4%
        * - SymPy test files
          - 612
          - 71,205
          - +8,842.4 (71.49%)
          - +97,952.4 (465.08%)
          - +1,241.1%


The corpus run includes all eligible ``.py`` files in CPython ``Lib`` and
the installed ``django``, ``html5lib``, and ``sympy`` package directories.
It excludes directories whose names start with ``test``, end with ``_test``,
or equal ``benchmarks``. It also excludes filenames that start with
``test_``. It does not select files by assertion count. No syntax failures
required an additional exclusion.

The JSON record lists every included
file with its hash and every excluded path with its reason. The rule also
excludes shipped test-support packages, such as ``django/test`` and
``sympy/testing``.

An earlier two-mode experiment selects all 612 ``test_*.py`` files under directories
named ``tests`` in SymPy 1.14.0. It compiles source with ordinary assertions
and with capture. It does not apply pytest rewriting or execute tests.

This corpus contains 71,205 assertions. Bytecode grows from 12,664,866 to
21,719,464 bytes. Marshal size grows from 21,566,850 to 121,870,093 bytes.

Median compile time grows from 1.285 to 17.228 seconds, about 13.4x.
Individual compile samples range from 1.22 to 1.76 seconds in ordinary
mode and from 12.79 to 25.09 seconds with capture. The host is shared.

The new three-mode comparison repeats this corpus with pytest as well.
Its compile times come from a separate run. The code sizes agree exactly
between runs for ordinary assertions and capture.
:download:`measure_test_sources.py <workload-evidence/measure_test_sources.py>`
records its file hashes, counts, sizes, and ten pairs of compile times.

Each compilation uses ``dont_inherit=True`` and ``optimize=0``. Capture
adds only ``ast.PyCF_ASSERT_DETAILS``. Totals include nested code objects.
Bytecode size includes inline caches. Marshal size includes code objects,
constants, capture plans, and source and exception tables. It excludes
``.pyc`` headers, interpreter memory, and native code.

The compiler run reads source bytes before timing. It executes ten pairs
in one process, with alternate mode order after warmup. Timing excludes
file access, imports, AST counting, and serialization.

The standard library
has 702 files, of which 162 contain assertions. Its 543 assertions add
29,202 bytes of bytecode and 277,041 bytes of serialized code. The last two standard library pairs
have large time increases in both modes. All samples remain in the record.
The table in these notes retains compile-time changes for every corpus.

The build uses GCC 15.2.0 and ``-O3``, without PGO, LTO, or the JIT.
The host is an AMD Ryzen AI Max+ 395 with 16 cores and 32 logical CPUs.
Runtime measurements use CPU 25. The four library corpora use CPU 3. The SymPy test corpus uses CPU 1.

The processes have CPU affinity, but the host is shared. The raw records
include load averages, build flags, executable and harness hashes, and
UTC timestamps. The `pyperf system guide
<https://pyperf.readthedocs.io/en/latest/system.html>`_ explains why CPU
affinity alone does not remove system noise.

Reproduction scripts are :download:`measure_workloads.py <workload-evidence/measure_workloads.py>` and :download:`measure_corpora.py <workload-evidence/measure_corpora.py>`. The paths in these scripts identify
the local prototype and package directory. After package installation,
these commands repeat the measurements with the prototype interpreter:

.. code-block:: console

    ./python /path/to/workload-evidence/measure_workloads.py
    ./python /path/to/workload-evidence/measure_corpora.py
    ./python /path/to/workload-evidence/measure_test_sources.py

The :download:`upstream manifest <workload-evidence/upstream-sources.json>` supplies
the download URLs and destination paths for benchmark source and input.
The install command uses the exact versions in ``requirements.txt``:

.. code-block:: console

    python -m pip install --no-compile --target workload-evidence/vendor \
        -r workload-evidence/requirements.txt

The :download:`archive <snazzy-asserts-assets.zip>` contains measurement scripts,
manifests, raw records, and benchmark source and input.
It includes the measured pytest and dependency source with their licenses.
It excludes the installed workload packages, which the install report pins.
Cold filesystem imports, peak memory, and current end-to-end failure
latency still need measurements.

Earlier records
~~~~~~~~~~~~~~~

The 18 October records remain available for comparison:
:download:`assertion loops <evidence/loop-benchmark.json>`,
:download:`selected-module corpus <evidence/corpus.json>`,
:download:`bytecode sizes <evidence/sizes.json>`, and
:download:`warm formatter calls <evidence/formatter-latency.json>`.
The earlier corpus selected only files that contain assertions.
Its size percentages do not describe the whole standard library.

The old pytest series calls ``rewrite_asserts()`` directly on the same
source. It excludes collection, plugins, and failure reports. Its 1.67x
geometric mean and the compiler's 1.86x mean describe generated assertion
loops. Neither estimates complete test-suite runtime.
Raw records also contain earlier success-event experiments that the PEP
excludes. Current end-to-end failure latency remains unmeasured.

The worked ``check()`` example uses 38 bytecode bytes and three local slots
in ordinary mode. Capture uses 100 bytes and nine slots. The :download:`example checks <evidence/examples-check.json>` and :download:`disassembly <evidence/worked-example.dis>` record those results.

``evidence-manifest.json`` identifies the older records and prototype patch.
The new ``workload-evidence/manifest.json`` records hashes for this revision.
It includes a :download:`prototype patch <workload-evidence/prototype.patch>` against
CPython commit ``b00a14018172652226bd6efb517af021bd03aa88``. The runtime
record also identifies the measured executable by its SHA-256 hash.
The `published prototype
<https://github.com/pablogsal/cpython/tree/d944fbc4015388d800d872614bc9c4ab565897a0>`_
contains the implementation and a note on its remaining work.

Capture code is in ``Python/codegen_assert.h``, dispatch is in
``Python/intrinsics.c``, and the API is in ``Lib/assertionlib.py``.
``Tools/assert_details/README.rst`` gives reproduction commands.

``sources.json`` identifies the earlier public sources and local snapshots.
Public documentation under ``stable`` or ``/3/`` can change. The benchmark
source links use a fixed revision.


Editorial references
--------------------

The shorter draft uses the example-first motivation of
`PEP 657 <https://peps.python.org/pep-0657/>`_ and the concrete specification
sections of `PEP 701 <https://peps.python.org/pep-0701/>`_ and
`PEP 758 <https://peps.python.org/pep-0758/>`_. Pablo Galindo Salgado is a
coauthor of these PEPs. They are style references, not evidence that this
proposal is accepted.

The performance section follows the distinction in
`PEP 709 <https://peps.python.org/pep-0709/#reference-implementation>`_ between an
isolated operation and a workload that uses it. Its results do not supply
evidence for this prototype.

The requested `Wikipedia style checklist
<https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing>`_ informed
cuts to repeated explanations, generic framing, and excessive headings.
It is not a technical source for the PEP or proof of authorship.
