# Clone Operator

51 source transformations for studying code clone detection, implemented for Java and C11. Each operator has an independent implementation in each language. The C implementation includes the broader applicability profile `C_ENTRY_INSERTIONS_V2` used in the experiments.

## Setup

Python 3.11 is recommended. The SCT API and command line need only the three Tree-sitter packages and do not download language models.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-sct.txt
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
```

## Apply an operator

The `sct` API uses the operator IDs printed in the paper.

```python
from sct import create_operator

source = "int f(int n){int a[2]={3,4};return n+a[0];}"
result = create_operator("SD2", language="c", seed=42).apply(source, k=1)
print(result.code)
print(result.successful)
print(result.rejections)
```

For a Java method, omit `language` or use `language="java"`. `k` limits successful applications of that operator. Inapplicable inputs remain unchanged and include rejection information.

```bash
python -m sct --list
python -m sct --language c --operator SD2 -k 1 --input examples/array.c --output transformed.c --log transformed.json
```

Output and log files must not already exist. Omitting `--output` writes the transformed source to stdout.

## Compose all 51 operators

```python
from sct import compose_all51

result = compose_all51(source, language="c", seed=42)
print(result["code"])
print(result["successful"])
print(result["trace"])
```

```bash
python -m sct --language c --all51 --input examples/array.c --output composed.c --log composed.json
python -m sct --language java --all51 --input examples/Example.java --output Composed.java --log composed-java.json
```

The composition follows seven phases, visiting finite snapshots of eligible locations. It tracks edits, protects regions against inverse transformations, and shares the initial location snapshot across insertion operators. All 51 operators are considered, but the number of applicable operators depends on the input. This differs from applying each operator once or repeatedly using a large `k`.

The default program ID is the input's SHA-256. `--program-id` supplies an explicit ID when reproducing a dataset run. Source, language, seed, program ID, and composition configuration determine the run. See the [composition configuration](src/sct/all51.json).

## Operator inventory

The [paper inventory](docs/operators.md) lists all 51 operators, their classification, counterparts, and scaling classes. The same information is available as [JSON](src/sct/operators.json) and through `sct.list_operators()`.

| Dimension | Groups and operator counts |
| --- | --- |
| Level | Word 9, Statement 20, Control 22 |
| Target | Identifiers 1, Constants 8, Expressions 10, Declarations 5, Ordinary statements 5, Conditionals 14, Loops 8 |
| Category | Replacement 35, Redundancy 12, Reordering 4 |

Use `sct.create_operator` for paper IDs. The lower-level `operators.create_strategy` retains implementation IDs for compatibility. Nine IDs differ between these interfaces. The inventory gives the mapping explicitly, and application records retain the implementation ID.

## C applicability

The C profile no longer rejects every candidate merely because an array, structure, union, enumeration, or generic expression occurs elsewhere in its function. Each candidate still undergoes the relevant operator checks. SD2, SS2, CC2, and CL1 can also insert fresh locals or isolated blocks at function entry in these functions. Scope-changing rules retain their own restrictions.

This does not add general C++ support or arbitrary pointer and aggregate rewriting. Unresolved preprocessor context and unsupported extensions remain rejected. For example, raw inputs containing `#include` or `#define` are not transformed by this frontend. Use functions with the required context already resolved. See [C applicability and validation](docs/c-applicability.md).

The operators are intended to preserve behavior under their applicability conditions. Parsing and candidate checks do not establish whole-program equivalence. Compile and test original and transformed programs in the same project environment when applying them to new code.

## Legacy Java interface

The original public operator names and `src/operate.py` remain available through compatibility adapters. These adapters use the current implementation and are not a promise of byte-for-byte output equivalence with the first release.

```python
from operators import ConditionReplace

operator = ConditionReplace(mode="if_to_switch_nesting", seed=42)
transformed = operator("int sign(int n){if(n==0)return 0;else return 1;}")
```

```bash
python src/operate.py condition-replace examples/Example.java -o legacy.java --seed 42
```

Model-based legacy renaming and sampling features need the optional dependencies in `requirements.txt`. For those features, install that file and the resources required by the selected provider, including `en_core_web_sm` and NLTK WordNet and words. Model-based renaming may download its configured pretrained model. The standard SCT entry point above uses fresh names without model downloads.

## Validation

```bash
python -m pip install -r requirements-test.txt
python -m unittest discover -s src/tests -p 'test_*.py'
```

Install GCC and a JDK to run compiled behavior checks. Tests cover the Java/C inventory, candidate checks, reproducibility, edit replay, compatibility, and the broader C fixtures at `-O0` and `-O2` with UBSan. Compiler-dependent tests report skips if the corresponding tool is unavailable. One optional legacy encoder test also requires PyTorch and is skipped when it is not installed.

The [release validation record](docs/validation.md) reports the executed checks.

Source provenance and packaging changes are recorded in [release-source.json](docs/release-source.json). The repository does not include evaluation datasets or model checkpoints. `data/variable_frequency_stats.json` is retained for the legacy sampling interface.
