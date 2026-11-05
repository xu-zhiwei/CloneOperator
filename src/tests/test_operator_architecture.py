"""Architecture boundaries and retained public compatibility capabilities."""
import ast
import importlib
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC))
from operators import REGISTRY, create_strategy
from operators.compatibility.imports import ALIASES


class ArchitectureTests(unittest.TestCase):
    def test_only_canonical_infrastructure_and_forty_strategies_exist(self):
        root = SRC / "operators"
        self.assertEqual(
            {p.name for p in root.iterdir() if p.is_dir() and p.name != "__pycache__"},
            {
                "base",
                "tools",
                "compatibility",
                "java",
                "c",
            },
        )
        self.assertEqual(
            {p.name for p in root.glob("*.py")},
            {"__init__.py", "registry.py", "taxonomy.py"},
        )
        forbidden = {"sct_impl", "condition_replace_impl", "loop_replace_impl"}
        for name in forbidden:
            self.assertFalse((root / name).exists())
        strategies = []
        for p in root.rglob("*.py"):
            self.assertNotRegex(p.stem, r"_v\d+$")
            tree = ast.parse(p.read_text())
            definitions = [
                node
                for node in tree.body
                if isinstance(node, ast.ClassDef)
                and any(
                    isinstance(n, ast.Assign)
                    and isinstance(n.value, ast.Constant)
                    and bool(n.value.value)
                    and any(
                        isinstance(t, ast.Name) and t.id == "strategy_id"
                        for t in n.targets
                    )
                    for n in node.body
                )
            ]
            if definitions:
                self.assertEqual(len(definitions), 1, p)
                strategies.append(definitions[0].name)
            if "compatibility" not in p.parts and p.name != "__init__.py":
                for n in ast.walk(tree):
                    if isinstance(n, ast.ImportFrom) and n.module:
                        self.assertNotIn("compatibility", n.module, p)
                        self.assertNotIn("sct_impl", n.module, p)
                        self.assertNotIn("replace_impl", n.module, p)
        self.assertEqual(len(strategies), 102)
        self.assertEqual(set(strategies), {cls.__name__ for cls in REGISTRY.values()})

    def test_all_deprecated_import_paths_resolve_without_files(self):
        for relative, target in ALIASES.items():
            with self.subTest(path=relative):
                module = importlib.import_module("operators." + relative)
                self.assertIsNone(getattr(module, "__file__", None))
                names = (
                    target
                    if isinstance(target, dict)
                    else getattr(module, "__all__", ())
                )
                for name in names:
                    self.assertIsNotNone(getattr(module, name))
        scope = {}
        exec("from operators.sct_impl.word.identifier.replacement import *", scope)
        self.assertIs(scope["IdentifierRenaming"], REGISTRY["WI1"])

    def test_compatibility_imports_and_model_construction_are_lightweight(self):
        script = """import sys
from operators import IdentifierRenameV4, ConstantReplace
from operators.identifier_rename_v4 import IdentifierRenameV4 as Old
assert Old is IdentifierRenameV4
op=IdentifierRenameV4(token_vocab=['count','size'])
assert not op.selector._initialized
assert not any(name in sys.modules for name in ('torch','transformers','spacy','nltk'))
"""
        subprocess.run(
            [sys.executable, "-c", script], cwd=SRC, check=True, capture_output=True
        )

    def test_name_selection_batches_and_binding_use_a_fixed_service(self):
        from operators import IdentifierRenameV4

        class Selector:
            def recommend(self, names):
                return {name: ("count", 0.9) for name in names if name == "value"}

        op = IdentifierRenameV4(token_vocab=["count"], name_selector=Selector())
        state = random.getstate()
        source = "int m(int value){return value;}"
        code, recommendations = op.operate(source)
        self.assertIn("int count", code)
        self.assertIn("return count", code)
        self.assertEqual(recommendations, {"value": ("count", 0.9)})
        self.assertEqual(random.getstate(), state)
        self.assertEqual(op(source.encode()), code.encode())

    def test_current_literal_candidates_preserve_ranges_and_types(self):
        from operators import (
            ConstantReplace,
            RedundantConstantInsert,
            ConstantReplaceV2,
        )

        vocab = [
            "(",
            ")",
            "+",
            "-",
            "*",
            "/",
            "!",
            "true",
            "false",
            "0",
            "1",
            "2",
            "3",
            "4",
            "7",
        ]
        source = "int m(){return 7;}"
        self.assertEqual(
            ConstantReplace(token_vocab=vocab)(source), "int m(){return (3 + 4);}"
        )
        self.assertEqual(
            ConstantReplace(token_vocab=vocab).operate(source.encode())[0],
            b"int m(){return (3 + 4);}",
        )
        self.assertNotEqual(RedundantConstantInsert(token_vocab=vocab)(source), source)
        op = ConstantReplaceV2(
            token_vocab=vocab, sample_one_constant_per_statement=True
        )
        code, recs = op.operate("int m(){return 7+7;}")
        self.assertEqual(len(recs), 1)
        self.assertNotEqual(code, "int m(){return 7+7;}")

    def test_conversion_adapters_dispatch_every_current_mode(self):
        from operators import ConditionReplace, LoopReplace
        from sct_cases import CASES

        for cls in (ConditionReplace, LoopReplace):
            for mode, sid in cls.modes.items():
                with self.subTest(mode=mode):
                    op = cls(mode=mode)
                    self.assertNotEqual(op(CASES[sid]), CASES[sid])
                    self.assertIsInstance(op(CASES[sid].encode()), bytes)

    def test_existing_reorder_defaults_do_not_exchange_back_the_same_site(self):
        from operators import StatementReorder, IdentifierReorder

        source = "int m(){int a=1;int b=2;return a+b;}"
        self.assertNotEqual(StatementReorder()(source), source)
        self.assertEqual(StatementReorder(max_swaps=0)(source), source)
        configured = StatementReorder(
            enabled_reorders="adjacent_single_decl_init, adjacent_multi_decl"
        )
        self.assertNotEqual(configured(source), source)
        expression = "int m(int a,int b){return a+b;}"
        self.assertNotEqual(IdentifierReorder()(expression), expression)
        self.assertEqual(IdentifierReorder(reorder_ratio=0)(expression), expression)

    def test_primitive_fragment_sampling_and_modes(self):
        from operators import RedundantStatementInsert

        payload = {
            "overall": {
                "variable_type_frequency": {"byte": 100},
                "variable_name_frequency_by_type": {"byte": {"counter": 1}},
                "variable_init_value_frequency_by_type": {"byte": {"127": 1}},
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.json"
            path.write_text(json.dumps(payload))
            for mode in ["def_only", "def_use", "inc_dec", "dec_inc", "random"]:
                op = RedundantStatementInsert(
                    stats_path=str(path),
                    stats_scope="overall",
                    analyzer_mode=mode,
                    type_sampling="frequency",
                )
                result = op("int m(){return 1;}")
                self.assertIn("byte counter", result)
                self.assertFalse(
                    create_strategy("SE1")
                    .parser.parse(result.encode())
                    .root_node.has_error
                )

    @unittest.skipUnless(importlib.util.find_spec("torch"), "optional legacy encoder test requires torch")
    def test_encoder_candidate_threshold_and_whitening_without_model_download(self):
        import torch
        import operators.tools.names as names
        from operators.tools.names import ModelNameSelector

        selector = ModelNameSelector(
            token_vocab=["count"], whitening_kernel_size=2, rename_similarity=0.8
        )
        with patch.object(names, "torch", torch, create=True):
            transformed = selector._compute_whitening(
                torch.tensor([[1.0, 0.0], [0.0, 1.0], [2.0, 1.0], [1.0, 3.0]])
            )
            self.assertTrue(torch.isfinite(transformed).all())
            self.assertTrue(
                torch.allclose(transformed.T @ transformed / 4, torch.eye(2), atol=1e-5)
            )
            selector._whitening_mu = torch.zeros((1, 2))
            selector._whitening_W = torch.eye(2)
            selector.vocab_embeddings = torch.tensor([[1.0, 0.0]])
            selector.tokenizer = lambda token, **kwargs: {
                "input_ids": torch.tensor([[0 if token == "value" else 1]])
            }
            embeddings = torch.nn.Embedding.from_pretrained(
                torch.tensor([[1.0, 0.0], [0.0, 1.0]])
            )
            selector.model = SimpleNamespace(
                device=torch.device("cpu"),
                embeddings=SimpleNamespace(word_embeddings=embeddings),
            )
            selector.english_words = set()
            selector.lemma_analyzer = lambda text: [SimpleNamespace(lemma_=text)]
            selector._initialized = True
            self.assertEqual(selector.recommend(["value"]), {"value": ("count", 1.0)})
            self.assertEqual(selector.recommend(["other"]), {})


if __name__ == "__main__":
    unittest.main()
