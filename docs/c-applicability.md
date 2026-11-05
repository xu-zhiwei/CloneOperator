# Broader C applicability

This release includes the frozen `C_ENTRY_INSERTIONS_V2` operator profile.
The candidate and function-entry checks match the implementation used for the
broader C coverage experiments. Java strategy files are unchanged from the
51-operator implementation recorded in `release-source.json`.

## Changes

The previous C candidate pipeline rejected an entire function if it contained
an array declarator, structure, union, enumeration, or generic expression.
The new pipeline lets the individual operator analyze its candidate instead.
This allows supported local integer expressions to be transformed even when
other parts of the function use more complex C constructs.

The existing SD2, SS2, CC2, and CL1 constructions can insert fresh declarations
or isolated redundant blocks at function entry. They do not move the original
declarations or rewrite array accesses. The other rules retain their existing
scope and type checks.

Global rejection of unresolved preprocessing and unsupported C extensions is
retained. Local checks for arithmetic types, escaped bindings, side effects,
qualifiers, and scope-changing edits still apply where implemented by each
operator. This is an applicability extension, not a general C or C++ frontend.

## Verification scope

`test_c_profile_release.py` exercises fixed arrays, structures, variable-length
arrays, and local pointers. It replays composition edits and compares original
and transformed outputs using GCC C11 at `-O0` and `-O2`, with undefined behavior
sanitization enabled. Separate checks exercise each of the four entry insertions
and verify rejection of unresolved macros.

These are controlled execution checks, not a proof of equivalence for all inputs
or all programs. A successful transformation means candidate checks and parsing
passed. It does not itself imply that the surrounding project compiles.

The older implementation-level examples and conditional semantic arguments are
preserved in `sct_c11.md` and `sct_semantic_contracts.md`. Their IDs are internal
implementation IDs. Use `operators.md` for paper IDs. The broader eligibility
described here supersedes the old blanket rejection of aggregate-containing
functions.
