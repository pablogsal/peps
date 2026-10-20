Measurements for the simplified assertion prototype, 20 October 2026.

Source: pablogsal/cpython, commit d944fbc4015388d800d872614bc9c4ab565897a0.
Base: b00a14018172652226bd6efb517af021bd03aa88.
Earlier prototype: 96d1d0a09d052dddcb9d026f93094ccca3a0db9d.

loops.json uses 9 rounds of 0.15 seconds per sample, with 1000 assertions per
function call. CPU 17. Modes run in shuffled order in the same executable.
The PEP uses the 11 cases listed in summary.json, which excludes constant True
and the three later arithmetic cases. The 14-case before/after comparison
uses all nonconstant cases. The earlier run uses 7 rounds of 0.08 seconds.
Shared-host timing does not establish a stable speed change between builds.

compile.json uses all six orders of plain, pytest rewrite, and compiler
capture on 612 fixed SymPy 1.14.0 files. Sizes include every nested code
object. Compilation timing excludes file IO, imports, and serialization.
The input manifest and pinned pytest sources are in the adjacent historical
evidence directories. Source bytes must match the manifest hashes.

measured_compile.py is the exact measurement script, with original local
paths. reproduce_compile.py accepts paths for another checkout. For example:

./python reproduce_compile.py --source-root /path/to/sympy \
    --evidence-root /path/to/unpacked-assets --output compile.json

The benchmark script accepts --pytest-source for a pytest checkout and
--pytest-deps for its installed dependencies. --callbacks measures the failure
handler paths. The recorded failure rows distinguish an absent assertionlib
module from a loaded module with no handler.

The corpus JSON files describe the same 162 production stdlib sources.
They contain 543 assertions. Unmodified code dominates these whole-module
sizes. The hashes in after-corpus.json identify their original source bytes.

The historical evidence files remain unchanged. prototype.patch describes
the current implementation. Exception pickle policy remains incomplete.
