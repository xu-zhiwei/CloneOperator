# Clone Operator

Semantic-preserving source-code transformations used in our code-clone
experiments. The current implementation targets Java and is built on
Tree-sitter.

## Operators

- identifier renaming and identifier reordering
- constant replacement and redundant constant insertion
- loop replacement (`for`, `while`, and `do-while`)
- condition replacement (`if`/`switch`)
- statement reordering and redundant statement insertion

## Setup

The code was developed with Python 3.11.

```bash
python -m venv .venv
python -m pip install -r requirements.txt
python -m spacy download en_core_web_sm
python -m nltk.downloader wordnet words
```

The first use of `IdentifierRename` downloads the configured pretrained model
from Hugging Face (CodeBERT by default).

## Usage

Add `src` to `PYTHONPATH`, then instantiate an operator and call it with Java
source code:

```python
from operators import ConditionReplace

source = """
class Example {
    int sign(int value) {
        if (value == 0) return 0;
        else return 1;
    }
}
"""

operator = ConditionReplace(mode="if_to_switch_nesting", seed=42)
transformed = operator(source)
print(transformed)
```

All public operators are exported from `src/operators/__init__.py`. Most
operators accept a `seed` argument for reproducible transformations and can be
applied repeatedly with `operator(source, k=n)`.

For directory-scale statement reordering, use:

```bash
python src/run_statement_batch.py \
  --input-dir path/to/java/files \
  --output-dir path/to/output
```

For a single Java file, the generic command-line entry point is:

```bash
python src/operate.py condition-replace Input.java -o Output.java --seed 42
```

## Data

`data/variable_frequency_stats.json` contains the variable-frequency statistics
used by the operators. `src/variable_frequency_stats.py` can regenerate these
statistics from separately obtained dataset artifacts.
