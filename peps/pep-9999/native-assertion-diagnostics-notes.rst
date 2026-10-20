:orphan:

Assertion diagnostics: technical notes
======================================

These notes accompany the PEP draft. They retain the detailed API contract,
prototype layout, and measurements from the longer version. Proposed behavior
and incomplete prototype behavior remain distinct throughout the notes.
The prototype now uses existing instructions and supports failure callbacks
only. Optimization still removes assertions.

Free-threaded builds, the machine-code JIT,
and callback isolation across subinterpreters still require verification.

Specification
=============

Compile Control
---------------

Capture is off by default. ``python -X assert_details`` enables it for
source compilation throughout the process. Libraries select the same
feature with ``ast.PyCF_ASSERT_DETAILS``. The C API accepts
``PyCF_ASSERT_DETAILS`` in ``PyCompilerFlags.cf_flags``.

.. code-block:: python

    import ast

    source = "assert price * quantity == expected"
    code = compile(
        source, "invoice.py", "exec",
        flags=ast.PyCF_ASSERT_DETAILS,
        dont_inherit=True,
    )

The flag applies to source or AST input and to nested functions and classes
in that compilation. It does not apply to modules imported by that code
or to later ``compile()`` calls. AST-only requests return an ordinary AST.

The command-line option also applies to ``compile()`` calls with
``dont_inherit=True``. It does not change code objects that already exist,
frozen modules, or bytecode supplied by a loader. There is no separate
disable option or per-compilation override for the process option.

``-O`` and ``-OO`` still remove assertions. The ``optimize`` argument to
``compile()`` follows its ordinary rules. A loader can select ``optimize=0``
for test modules that need assertions, even under ``-O``.

Import caches must distinguish code with capture from code without it.
The prototype appends ``-assert`` to the ordinary cache tag. The optimization
suffix from `PEP 488`_ remains separate. Custom loaders must include the
capture choice in their cache keys. ``py_compile`` and ``compileall`` use
the active interpreter option.

``sys._xoptions`` exposes the command-line option. The proposal adds no
environment variable or ``sys.flags`` attribute. CPython's interpreter-flag
helper forwards the option to child interpreters, including the standard
``multiprocessing`` spawn path. An independently constructed subprocess
command must include the option itself.

Capture Semantics
-----------------

An instrumented assertion evaluates its test with ordinary Python order
and short circuit behavior. Capture does not repeat expression evaluation,
comparison operations, or truth conversion. It does not call ``repr()``.

For example:

.. code-block:: python

    calls = []

    def left():
        calls.append("left")
        return 0

    def right():
        calls.append("right")
        return 1

    assert left() and right()

Only ``left()`` runs. The capture contains its result, ``0``.
The graph also identifies ``right()`` as an expression without a captured
result. No callback or formatter evaluates that expression later.

Comparisons can return objects other than ``bool``. Capture keeps the raw
comparison result and the truth result that the assertion actually uses.
The ``value`` and ``truth`` properties expose these separately:

.. code-block:: python

    calls = []

    class Verdict:
        def __bool__(self):
            calls.append("bool")
            return False

    class Item:
        def __eq__(self, other):
            calls.append("eq")
            return Verdict()

    assert Item() == Item()

After this failure, ``calls`` contains ``["eq", "bool"]``.
The comparison's ``value`` is the ``Verdict`` instance.
Its ``truth`` is ``False``. Access to either property adds no calls.

For a chain such as ``a < b < c``, each link has a separate comparison
record. The middle operand evaluates once. A skipped link has no captured
result. An evaluated link can have a raw result without a separate truth
conversion when its parent expression does not require that conversion.

If the condition fails, Python evaluates the optional assertion message
once, then constructs the exception. A failure callback runs after those
steps. If the test or message raises an exception, that exception propagates
normally. It does not become an assertion failure event.

Only an instrumented ``assert`` statement creates native diagnostic data.
An explicit ``raise AssertionError(...)`` does not create such data.

Capture retains references, not snapshots. If later expression evaluation
or the assertion message mutates an object, a report can show its changed
state. Retained references can delay ``__del__`` calls and weak-reference
callbacks. Additional allocations can fail. These are observable effects
of the optional mode.

If diagnostic support raises after the assertion exception exists, the
new exception must retain the assertion exception as its context.
This rule also applies to internal dispatcher errors, not just user callbacks.

Capture Scope
-------------

The graph describes expressions in the assertion test. It does not include
the assertion message or the internal execution of a called function.
A comprehension or generator expression exposes its result object.
It does not expose a record for each iteration.

The compiler can fold constants before capture instrumentation.
Consequently, the graph need not contain every node from the original AST.
Expression text is normalized source text, not an exact source-file slice.
Comments, quote choices, and spaces need not remain intact.

The API reports capture availability. A graph node can describe syntax
without a runtime value, such as a store target in an assignment expression.
Consumers must check ``evaluated`` before they access ``value``.
They must not infer a complete execution trace from the node list.
The generic kind ``expression`` means that no more specific kind applies.
A later Python version can assign a more specific kind to that syntax.

The proposal does not restrict ``await`` or ``yield`` within assertions.
A suspended frame retains its temporary captures until the assertion
completes or frame cleanup releases them. A callback uses the execution
context in which the assertion reaches the callback point.

Library API
-----------

The exception is the entry point. ``AssertionError.details`` returns the
captured ``AssertionDetails``, or ``None`` when no capture data exists.
The first access builds and caches the graph. Later accesses return it.
Other exception types do not gain a ``details`` attribute.

.. code-block:: python

    import ast

    code = compile("assert price * quantity == expected", "invoice.py", "exec",
                   flags=ast.PyCF_ASSERT_DETAILS, dont_inherit=True)
    try:
        exec(code, {"price": 18, "quantity": 3, "expected": 60})
    except AssertionError as error:
        details = error.details
        print(details.format())                    # assert (18 * 3) == 60
        print(details.comparisons[0].left.value)    # 54

``details.format(*, compare=None)`` returns text without a terminal newline.
It produces no output and does not invoke a scoped formatter.
It does not reevaluate the assertion, but can call user ``__repr__`` methods.
Default representations and built-in container differences have size limits.
Structural differences use supported exact built-in types, without custom
comparison, truth, hash, or iteration methods.

The optional ``compare(op, left, right)`` receives captured operands for each
evaluated comparison, including successful links in a failed chain.
It does not receive skipped links. Its result has these meanings:

* ``None`` selects the default explanation.
* A nonempty string supplies custom text. Its first line replaces the
  comparison summary. Later lines supply detail.
* An empty string keeps the summary and suppresses the default difference.

Other return types raise ``TypeError``. Formatter errors propagate.

.. code-block:: python

    def explain_total(op, left, right):
        if op == "==" and type(left) is int and type(right) is int:
            return f"total differs by {right - left}"
        return None

    text = details.format(compare=explain_total)

Data Objects
------------

The public objects have immutable attributes. Their captured operand
objects can still be mutable. The tables below define attributes that
consumers can read. They do not define a serialized representation or
require a particular implementation of these classes.
The classes are return types for this API. Public construction, dataclass
helpers, and positional pattern-match fields are outside this contract.

.. list-table:: ``AssertionDetails``
    :header-rows: 1
    :widths: 28 72

    * - Attribute
      - Description
    * - ``expression``
      - Normalized text for the assertion test.
    * - ``location``
      - A ``SourceLocation`` for that test.
    * - ``root``
      - The top-level ``Expression`` node.
    * - ``nodes``
      - A tuple of all expression nodes in this graph.
    * - ``comparisons``
      - A tuple of comparison records. Links within a chain follow
        source order.

.. list-table:: ``Expression``
    :header-rows: 1
    :widths: 28 72

    * - Attribute
      - Description
    * - ``id``
      - An integer unique within this graph.
    * - ``text``, ``kind``
      - Normalized expression text and a structural kind.
    * - ``location``
      - The expression's ``SourceLocation``.
    * - ``children``
      - A tuple of child ``Expression`` nodes in evaluation order.
    * - ``evaluated``
      - Whether a captured result is available.
    * - ``value``
      - The original result object. Raises ``ValueError`` if unavailable.
    * - ``truth``
      - A truth result from execution, or ``None`` if unavailable.

Kinds include ``name``, ``constant``, ``binary``, ``unary``, ``not``,
``and``, ``or``, ``conditional``, ``call``, ``attribute``, ``subscript``,
``compare``, and the general kind ``expression``.
Consumers must tolerate additional kinds in future Python versions.

The graph also retains alternatives that do not execute.
For a conditional expression, children are the condition, body, and
alternative, in that order. Comparison records from distinct expressions
have no specified global order.
Node IDs do not identify variables or persist across separate failures.
Two occurrences of the same source expression have distinct nodes.

An available ``value`` of ``None`` differs from an unavailable value.
The ``truth`` property never calls ``bool(value)`` to fill a gap.
It can derive a result from captured truth results without user calls.
For example, ``not`` inverts its operand's captured truth result.
For ``and`` and ``or``, the node's value can come from the operand that
the expression selects.
The compiler need not create an extra runtime object for that purpose.

.. list-table:: ``Comparison``
    :header-rows: 1
    :widths: 28 72

    * - Attribute
      - Description
    * - ``operator``
      - One of Python's comparison operator strings.
    * - ``left``, ``right``
      - The operand ``Expression`` nodes.
    * - ``expression``
      - The parent comparison expression node.
    * - ``text``
      - Normalized text for this comparison link.
    * - ``evaluated``, ``value``, ``truth``
      - Availability, raw result, and recorded truth for this link.

``Comparison.value`` raises ``ValueError`` when no result is available.
A chain has one record per link. This includes skipped links.

``SourceLocation`` has ``filename``, ``lineno``, ``col_offset``,
``end_lineno``, and ``end_col_offset`` attributes. Line numbers start at 1.
Columns use zero-based UTF-8 byte offsets, as AST locations do.
End offsets are exclusive.

For AST input, locations reflect the supplied
AST positions. They need not refer to an actual source file.
Capture locations remain available with ``-X no_debug_ranges``.

Custom explanations
-------------------

``assertionlib.formatter(callback)`` installs a synchronous formatter in the
current execution context. Its argument must be callable or ``None``.
An invalid argument raises ``TypeError`` on entry to the scope.

.. code-block:: python

    import assertionlib

    def explain(details):
        return "Order mismatch:\n" + details.format()

    with assertionlib.formatter(explain):
        exec(code, {"price": 18, "quantity": 3, "expected": 60})

The callback receives one details object. A string result supplies the
explanation. Python prefixes the original assertion message, if present,
and stores the combined text in ``error.args``. The traceback displays it
once. An empty string omits the explanation. ``None`` preserves the original
arguments and default traceback behavior. Other return types raise ``TypeError``.

The callback runs after assertion message evaluation, before the exception
reaches its caller. It cannot suppress the assertion. If the callback or
support code raises, its error retains the assertion as ``__context__``.
The assertion retains any earlier exception context. During the callback,
``sys.exception()`` returns the assertion, which has no traceback yet.

Recursive assertions within an active formatter do not invoke another
formatter, including through nested formatter scopes. They still retain
capture data. Suppression ends when the callback returns or raises.
Successful assertions perform no callback lookup.

The dispatcher does not await callback results. Callbacks must be synchronous.
A coroutine result raises ``TypeError``, like any other non-string result.

Nested scopes replace the formatter. ``formatter(None)`` suspends it.
Exit restores the previous formatter. Context copies and new asyncio tasks
inherit it. Threads follow ``sys.flags.thread_inherit_context`` and an explicit
thread context, under the normal `contextvars documentation`_.
The context manager does not enable compiler capture.

Data Lifetime and Serialization
-------------------------------

CPython clears temporary captures when an assertion completes or exits
through an exception. On failure, the exception and any retained details
objects own references to the captured objects.

Normal use needs no explicit cleanup. For saved reports, retain text or a
``traceback.TracebackException``. A consumer that retains the exception can
set ``error.details = None`` to remove its payload and cached graph.
Repeated assignment of ``None`` is permitted. Other assigned values raise
``TypeError``. Separate details objects and traceback frames can still retain
operands. This operation does not clear the traceback or undo a custom message.

The exception's reduction protocol omits native capture data and its cached
graph. It preserves ordinary arguments and user attributes. A restored
exception has ``details is None``. Copies that use the reduction protocol
follow the same rule. The API defines no portable format for a separate graph.
A remote reporter can send formatted text or an explicit data schema.

Traceback Output
----------------

The standard traceback API includes explanations in ``format_exception``,
``format_exception_only``, ``print_exception``, and ``TracebackException``.
The normal interpreter exception hook uses the same output.
Consumers such as the default ``logging`` formatter inherit that behavior when
they delegate to the traceback module. Custom exception hooks control their
own output.

The explanation follows the exception's type and message, before its notes.
Exception groups apply the same rule to each contained assertion error.
``TracebackException`` formats the explanation when it constructs its
summary. It retains the explanation strings, not the captured operands.
Consequently, its constructor can execute object representation methods.

If the diagnostic formatter raises an ``Exception``, the standard traceback
path keeps the ordinary exception report and adds an unavailable-data line.
It does not suppress ``KeyboardInterrupt`` or ``SystemExit``.
An explicit ``details.format()`` call still propagates formatter errors.
A custom explanation already in ``error.args`` appears once.


CPython Implementation
======================

This section describes the prototype and its internal data layout.
The public API does not require other implementations to use these
instructions, temporary names, or tuple layouts.

From Source to Capture Instructions
-----------------------------------

The parser still creates an ordinary ``Assert`` AST node.
No grammar change or parser-level source rewrite is necessary.
The normal AST and symbol-table passes precede bytecode generation.
After code generation, the control-flow optimizer processes the instruction
graph. The assembler produces the code object and its exception tables.
Capture instructions and metadata pass through those stages with ordinary
instructions.

Consider this complete function:

.. code-block:: python

    def check(price, quantity, expected):
        assert price * quantity == expected

The assertion test contains these relevant nodes:

.. code-block:: text

    Compare: price * quantity == expected
      BinOp: price * quantity
        Name: price
        Name: quantity
      Name: expected

``codegen_assert()`` first applies the assertion-removal rule.
For an assertion that remains, the diagnostic flag selects capture code.
The compiler then creates an assertion context with a node graph, capture
records, and temporary slot assignments.

The expression visitor adds a node descriptor before it emits the normal
instructions for that node. After the instructions produce a result, the
visitor emits ``STORE_FAST slot; LOAD_FAST slot`` to retain the result in a hidden local.
The result remains available on the operand stack for its normal consumer.

For straight-line expressions, the rule is conceptually:

.. code-block:: text

    save the current parent node
    enter the expression node in the diagnostic graph
    emit its normal evaluation, with capture active for child expressions
    assign a hidden local slot to this result
    emit STORE_FAST followed by LOAD_FAST for that slot
    leave the result on the operand stack
    restore the saved parent node

This rule alone does not implement short circuit expressions.
The branch compiler also records the truth results that select each branch.
It emits captures within the branch that actually evaluates an expression.
A jump over that branch also jumps over its capture instructions.
The compiler records each comparison link separately for chains.

Temporary Storage and Metadata
------------------------------

For the example function, the first three frame slots hold the arguments.
The compiler assigns six more slots:

.. list-table::
    :header-rows: 1

    * - Frame slot
      - Internal name
      - Captured result for ``check(18, 3, 60)``
    * - 3
      - ``.assertion.0``
      - ``price``: ``18``
    * - 4
      - ``.assertion.1``
      - ``quantity``: ``3``
    * - 5
      - ``.assertion.2``
      - ``price * quantity``: ``54``
    * - 6
      - ``.assertion.3``
      - ``expected``: ``60``
    * - 7
      - ``.assertion.4``
      - Raw comparison result: ``False``
    * - 8
      - ``.assertion.5``
      - Truth result: ``False``

These are entries in the current frame's ``localsplus`` array.
They are not module globals or Python dictionaries. Each entry retains
an object reference. An internal local marker hides them from ``locals()``.
Their internal names appear in ``co_varnames``, and ``co_nlocals`` grows.
The compiler reuses temporary slots for later assertions in the same scope.

Slot 7 supplies the comparison result. The graph uses the last evaluated
link as the comparison expression's value. It needs no duplicate capture.

The code object's ``co_consts`` contains a constant capture plan.
The plan associates slots with expression text, source spans, node IDs,
and record kinds. For example, one record connects slot 5 to
``price * quantity`` and its binary-expression node.
The runtime uses this record to interpret slot 5. The actual record is:

.. code-block:: python

    (5, "value", 1, None)

Its fields are the frame slot, record kind, node ID, and optional comparison
metadata. Node 1 describes the multiplication and stores its text and span.

The plan itself is ``(records, nodes)``.
Each node entry is ``(text, kind, span, child_ids)``. Its ID is its index.
Record kinds are ``value``, ``comparison``, and ``truth``.
A comparison record's extra data contains ``(operator, left_id, right_id)``.
Operand node IDs identify the captured operands. There is no separate map
from expressions to slots.

A slot starts with CPython's null stack reference. An unexecuted capture
leaves it null. The null reference differs from the Python object ``None``.
The failure payload uses ``()`` for an unavailable value and ``(value,)``
for an available value. Thus, ``(None,)`` represents an available ``None``.

The prototype's plan contains only marshal-compatible constants.
It contains no callback objects or imported modules.
Compilation creates the plan once. Each function invocation supplies its
own captured values in its own frame.

Existing Bytecode
-----------------

Capture uses ``STORE_FAST slot; LOAD_FAST slot``. Cleanup uses
``LOAD_FAST_AND_CLEAR slot; POP_TOP``. ``POP_TOP`` accepts a null reference,
so the same cleanup sequence handles evaluated and skipped expressions.
Both sequences use the existing optimizer and reference-ownership rules.
The implementation adds no opcodes.

The excerpt below omits offsets, caches, and exception-table details.
It shows the central sequence for the example:

.. code-block:: text

    LOAD_FAST_BORROW    price
    STORE_FAST         3
    LOAD_FAST          3
    LOAD_FAST_BORROW    quantity
    STORE_FAST         4
    LOAD_FAST          4
    BINARY_OP          *
    STORE_FAST         5
    LOAD_FAST          5
    LOAD_FAST_BORROW    expected
    STORE_FAST         6
    LOAD_FAST          6
    COMPARE_OP         ==
    STORE_FAST         7
    LOAD_FAST          7
    TO_BOOL
    STORE_FAST         8
    LOAD_FAST          8
    POP_JUMP_IF_TRUE    success

    LOAD_COMMON_CONSTANT AssertionError
    PUSH_NULL
    CALL               0
    LOAD_CONST         capture_plan
    CALL_INTRINSIC_2   INTRINSIC_ASSERT_DETAILS
    RAISE_VARARGS      1

    success:
    LOAD_FAST_AND_CLEAR 3
    POP_TOP
    ...
    LOAD_FAST_AND_CLEAR 8
    POP_TOP
    LOAD_COMMON_CONSTANT None
    RETURN_VALUE

    exception_cleanup:
    LOAD_FAST_AND_CLEAR 3
    POP_TOP
    ...
    LOAD_FAST_AND_CLEAR 8
    POP_TOP
    RERAISE            0

The ``CALL 0`` instruction constructs the exception instance before the
intrinsic call. Exception cleanup also clears all capture slots before
it reraises an error. This includes errors during operand evaluation.

``CALL_INTRINSIC_2`` already exists. ``INTRINSIC_ASSERT_DETAILS`` is a new
operation for that instruction.
The intrinsic receives the exception and the plan. It returns the same
exception for ``RAISE_VARARGS``.

On failure, it reads the slots named in the plan and attaches a private
payload to the exception. A consumer constructs the public graph lazily.
An ordinary successful assertion creates no Python diagnostic containers
and performs no callback lookup. It still executes capture and cleanup
instructions and retains temporary references.

How the Callback Runs
---------------------

The compiler does not emit the name of a user's callback.
The user imports ``assertionlib`` and passes a callable to ``formatter()``.
The module stores that callable in a ``ContextVar``.

The runtime path is:

.. code-block:: text

    assert executes capture instructions
        -> assertion fails
        -> INTRINSIC_ASSERT_DETAILS establishes the exception context
        -> it reads the frame slots and attaches the payload
        -> it finds an already imported assertionlib module
        -> assertionlib._dispatch(error) reads the current formatter
        -> callback(error.details) returns text or None
        -> the dispatcher installs custom text when supplied
        -> the assertion raises the exception

The C code uses ``PyImport_GetModule()`` to find an imported module in
``sys.modules``. This lookup does not import ``assertionlib`` from disk.
If the module exists, C calls its dispatcher with ``PyObject_CallOneArg()``.
The dispatcher checks the current formatter. Without a formatter, it returns.
The failure retains its capture data in both cases.

The dispatcher calls the callable object. A closure, bound method, or
callable instance works. No function-name lookup or source evaluation is
necessary. All diagnostic support runs with the assertion as the handled
exception. A support error retains the assertion as its exception context.

Module lookup is a prototype constraint. Reload of ``assertionlib`` replaces
its formatter variable. Removal from ``sys.modules`` disables dispatch.

The standard traceback path can later import formatter support lazily.
That import is separate from callback dispatch. Failure capture itself
does not require an application to import ``assertionlib``.

The prototype formatter reparses compiler-generated node text for the
expression kinds that it expands. Its private node layout must agree with
that parse. Library consumers must use the public graph instead of this
private formatter convention.


Earlier Performance Measurements
================================

The measurements below describe the prototype before the simplification
on 20 October 2026. They retain the earlier baseline, including its custom
opcodes. The research notes contain the current results.

The PEP summarizes assertion-loop cost and the comparison with pytest on
SymPy test sources. The :doc:`research notes <native-assertion-diagnostics-research>` contain the library workloads,
source corpora, methods, and raw records. This section retains the detailed
microbenchmarks.

Capture costs time even when an assertion succeeds. The prototype adds
reference operations, hidden local slots, cleanup, and metadata.
Some expressions also lose compiler shortcuts that omit intermediate
objects. A method call is one example.

The measurements below use a GCC 15.2.0 release build with ``-O3``.
The build does not use PGO, LTO, or the machine-code JIT.
The loop harness pins execution to CPU 17 on a shared host.
It uses nine samples, a target of 150 milliseconds per sample, and 1,000
assertions per function call. Mode order varies after warmup.

Each ratio compares native capture with ordinary assertions in the same
executable. It includes loop and harness costs. The byte counts come from
separate functions with one assertion and include inline cache bytes.
They exclude capture plans and exception tables. The corpus measurements
below include serialized metadata.

The worked ``check(price, quantity, expected)`` example uses 38 bytecode
bytes in ordinary mode and 100 with capture. Its local-slot count increases
from 3 to 9. The table uses the expressions from the benchmark harness:

.. list-table:: Selected successful-assertion measurements
    :header-rows: 1

    * - Case
      - Native / ordinary time
      - Ordinary bytecode
      - Native bytecode
    * - ``a == b`` (integers)
      - 2.16x
      - 24 bytes
      - 74 bytes
    * - ``a * 2 + b == expected``
      - 2.11x
      - 54 bytes
      - 126 bytes
    * - ``normalize(a) == b``
      - 1.25x
      - 44 bytes
      - 106 bytes
    * - ``a.strip().lower() == b``
      - 2.63x
      - 82 bytes
      - 158 bytes
    * - ``a > 0 and b > 0 and expected > 0``
      - 2.59x
      - 54 bytes
      - 166 bytes
    * - ``0 < a < b < expected``
      - 2.21x
      - 64 bytes
      - 162 bytes
    * - ``all(x >= 0 for x in a)``
      - 1.17x
      - 180 bytes
      - 154 bytes

The generator case has smaller bytecode because capture disables a fast
path for ``all()``. Ordinary code contains both a specialized loop and a
fallback call. Capture uses the ordinary call alone. Both byte counts
include the unchanged generator code object.

The geometric mean across eleven nonconstant cases is 1.86x.
The same cases give 1.67x for pytest's rewrite, relative to ordinary asserts.
The additional cases are attribute access, subscript access, short circuit
``or``, and list equality.
These results do not estimate whole-application slowdown or establish
superiority over pytest. The host's load average was approximately 20 to 24.
Controlled measurements remain necessary before release decisions.

The earlier corpus selected 162 library files that contain assertions.
It has 543 assertions and excludes library files without assertions.
Totals include 11,543 code objects. Some contain no assertions.
Capture increases bytecode from 2,868,200 to 2,897,402 bytes, or 1.02%.
Marshal size increases from 7,423,551 to 7,700,592 bytes, or 3.73%.

Median compile time increases from 0.462 to 0.481 seconds, or 4.07%.
The compile benchmark uses eight samples with alternate mode order.

The current compact formatter has these warm latencies:

.. list-table:: Formatting an existing failure payload
    :header-rows: 1

    * - Case
      - Median time
    * - Arithmetic comparison
      - 18.21 microseconds
    * - Function call comparison
      - 34.85 microseconds
    * - List comparison
      - 14.61 microseconds

Each result uses seven samples with 5,000 calls per sample on CPU 17.
These numbers exclude exception capture, cold imports, and traceback output.
Current end-to-end failure latency still needs a separate measurement.


Backwards Compatibility
=======================

Without the new controls, compilation retains ordinary assertion behavior.

The ordinary-mode signature check compares the simplified prototype with
unmodified CPython at the same base commit. All 162 files match. These signatures compare opcode names and
arguments, constants, local names, flags, and exception and location tables.
They also compare stack size and nested code. They ignore numeric opcode IDs.
That check does not establish zero runtime overhead across all workloads.

The optional capture mode preserves operand order, short circuit behavior, and
normal assertion messages. It adds reference retention, possible
allocation failures, and any effects of explicit callbacks or formatters.
Programs that inspect reference counts or weak references can observe a
different assertion result. For example, a temporary object can remain alive
through ``weakref.ref(make())()`` under capture. Ordinary execution can
release it before the weak reference call.

The prototype's cleanup handler also affects monitoring events.
A failed assertion emits ``RAISE``, ``EXCEPTION_HANDLED``, and ``RERAISE``
where ordinary compilation emits ``RAISE``. Tools must account for these
internal cleanup events. Capture also consumes one compiler block.
Code near the static block limit can reach that limit sooner.

The additional traceback lines also affect exact exception-output checks.
For example, ``doctest`` currently rejects an expected bare ``AssertionError``
when capture adds an explanation. Its integration needs a display policy.

The new flag occupies an unused compiler-flag bit in CPython.
The new intrinsic and private plan layout require a bytecode magic-number change.
Bytecode numbers, hidden names, and private capture payloads are not stable
APIs. Other Python implementations can provide the public contract through
different mechanisms.


References
==========

.. _pytest assertion documentation:
   https://docs.pytest.org/en/stable/how-to/assert.html

.. _PEP 657:
   https://peps.python.org/pep-0657/

.. _PEP 678:
   https://peps.python.org/pep-0678/

.. _contextvars documentation:
   https://docs.python.org/3/library/contextvars.html

The `assert statement reference`_ defines the current evaluation and
optimization rules. `PEP 1`_ and `PEP 12`_ define the PEP process and format.

.. _assert statement reference:
   https://docs.python.org/3/reference/simple_stmts.html#the-assert-statement

.. _PEP 488: https://peps.python.org/pep-0488/
.. _PEP 669: https://peps.python.org/pep-0669/
.. _AssertionLib package: https://pypi.org/project/AssertionLib/

.. _PEP 1: https://peps.python.org/pep-0001/
.. _PEP 12: https://peps.python.org/pep-0012/
