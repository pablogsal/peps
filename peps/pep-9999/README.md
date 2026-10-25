# Snazzy Asserts draft

[PEP source](../pep-9999.rst) · [PDF](snazzy-asserts.pdf)

9999 is a temporary number for this branch. No PEP number is assigned.
The PDF retains the unnumbered draft header. A discussion URL is still pending.

[Prototype implementation](https://github.com/pablogsal/cpython/tree/07781c3b5925868d41fee9da762cb0015a47c33b)

The technical notes contain the detailed API contract. The research notes
contain the methods, sources, and results. Local download links refer to
copies of the original records. The evidence archive contains the complete
measurement inputs, scripts, source snapshots, and licenses.

The prototype uses existing instructions and one assertion-details flag.
The API exposes ``error.details``, ``details.format()``, and a scoped formatter.
Exception serialization omits captured values and the cached graph.
