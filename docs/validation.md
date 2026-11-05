# Release validation

Validated on 2026-11-05 using Python 3.11, GCC, and the OpenJDK 11 compiler module.

- A clean virtual environment installed `requirements-test.txt` successfully.
- The full suite ran 105 tests with 104 passes and one skip. The skipped test
  requires the optional PyTorch encoder dependency. That test passed separately
  in the existing environment as part of the nine architecture and compatibility
  tests.
- Java and C each expose 51 strategies. The paper interface checks all mappings,
  including the nine IDs that differ from the internal registry.
- The four broader C fixtures compiled and executed at `-O0` and `-O2` with
  UBSan. Original and transformed outputs agreed for integer inputs 1 through 9.
- For those four fixtures, the released composition reproduced the frozen
  experiment's code and complete edit trace using the same seed and program ID.
- The Java/C command-line examples and the original Java command-line interface
  ran successfully in the clean environment.

The 199 operator source files match the frozen source hashes except for the two
documented compatibility export files. These packaging changes restore the
original public `IdentifierRename` name without changing strategy algorithms.
The batch composer and seven-phase configuration retain their frozen hashes.

Controlled fixtures and finite tests establish behavior on the checked cases.
They do not constitute a proof of equivalence for arbitrary programs or inputs.
