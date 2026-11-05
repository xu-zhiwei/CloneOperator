import json
from pathlib import Path
import random
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from operators.sct_core import Context
from operators.sct_impl.analysis import SemanticContext, walk
from operators.sct_strategies import create_strategy, REGISTRY


class SemanticAnalysisTests(unittest.TestCase):
    def context(self, source):
        return SemanticContext(source, create_strategy("SE1").parser)

    def test_disjoint_scopes_resolve_distinct_symbols(self):
        ctx = self.context("int m(){int a=0;{int x=1;a+=x;}{int x=2;a+=x;}return a;}")
        symbols = [s for s in ctx.symbols if s.name == "x"]
        self.assertEqual(len(symbols), 2)
        self.assertNotEqual(symbols[0].key, symbols[1].key)
        for symbol in symbols:
            references = ctx.references_of(symbol)
            self.assertEqual(len(references), 1)
            self.assertIs(ctx.resolve(references[0]), symbol)

    def test_unrelated_object_creation_does_not_disable_integer_analysis(self):
        source = "int m(int a,int b){Object unused=new Object();return a+b;}"
        self.assertEqual(create_strategy("SE1").apply(source).successful, 1)

    def test_exception_effects_and_dependencies(self):
        for source in [
            "int m(int a,int b){a/=b;b++;return a+b;}",
            "int m(int a,int b){a=b;b=a;return a+b;}",
        ]:
            result = create_strategy("SS1").apply(source)
            self.assertEqual(result.successful, 0)
            self.assertTrue(result.rejections)
        source = "int m(int a,int b){a=a/2;b++;return a+b;}"
        self.assertEqual(create_strategy("SS1").apply(source).successful, 1)

    def test_effect_cache_does_not_acquire_assignment_writes(self):
        ctx = self.context("int m(int a,int b){a=b+1;return b;}")
        assignment = next(n for n in ctx.nodes if n.type == "assignment_expression")
        rhs = assignment.child_by_field_name("right")
        self.assertTrue(ctx.effects(rhs).pure)
        self.assertTrue(ctx.effects(assignment).writes)
        self.assertTrue(ctx.effects(rhs).pure)

    def test_inline_rejects_changed_inputs_and_promotion(self):
        cases = [
            "int m(int a){int t=a+1;a++;return t;}",
            "long m(int a){long t=1;return t+a;}",
        ]
        for source in cases:
            result = create_strategy("SS5").apply(source)
            self.assertEqual(result.successful, 0)
            self.assertTrue(
                any(
                    r["reason"]
                    in {
                        "initializer_inputs_change_before_use",
                        "inlining_changes_numeric_promotion",
                    }
                    for r in result.rejections
                )
            )

    def test_capture_is_not_renamed(self):
        source = "int m(){int a=1;java.util.function.IntSupplier f=()->a;return f.getAsInt();}"
        result = create_strategy("WI1", selection="first").apply(source)
        self.assertNotIn("()->count", result.code)
        self.assertTrue(
            any(
                r["reason"] == "rename_has_capture_or_ambiguous_binding"
                for r in result.rejections
            )
        )

    def test_explicit_classes_and_metadata(self):
        self.assertTrue(
            all(
                cls.__module__.startswith(
                    ("operators.java.word.", "operators.java.statement.", "operators.java.control.")
                )
                for cls in REGISTRY.values()
            )
        )
        result = create_strategy("SD4").apply("int m(){int x=1;return x;}")
        self.assertEqual(result.changes[0]["construction"], "split_initialization")
        self.assertGreater(result.eligible_candidates, 0)

    def test_constructor_modes_validate(self):
        for sid, options in [
            ("SD1", {"enabled_reorders": ["misspelled"]}),
            ("CC1", {"mode": "wrong"}),
            ("CL7", {"mode": "wrong"}),
            ("SE2", {"modes": []}),
            ("SS4", {"extract": "wrong"}),
        ]:
            with self.assertRaises(ValueError):
                create_strategy(sid, **options)

    def test_typed_frequency_sampling_uses_matching_buckets(self):
        stats = {
            "overall": {
                "variable_type_frequency": {"int": 1, "String": 100},
                "variable_name_frequency_by_type": {
                    "int": {"integerName": 1},
                    "String": {"textName": 100},
                },
                "variable_init_value_frequency_by_type": {
                    "int": {"7": 1},
                    "String": {"null": 100},
                },
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.json"
            path.write_text(json.dumps(stats))
            options = dict(
                stats_path=str(path),
                java_types=["int"],
                type_sampling="frequency",
                name_sampling="frequency",
                init_sampling="frequency",
            )
            state = random.getstate()
            result = create_strategy("SD2", **options).apply("int m(){return 1;}")
            self.assertIn("int integerName0 = 7;", result.code)
            self.assertNotIn("textName", result.code)
            self.assertEqual(state, random.getstate())

    def test_ranked_name_threshold(self):
        def ranker(old, names):
            return [0.9 if n == "bestName" else 0.1 for n in names]

        op = create_strategy(
            "WI1",
            candidate_source="ranked",
            token_vocab=["bestName", "lowName"],
            ranker=ranker,
            min_similarity=0.8,
        )
        result = op.apply("int m(int a){return a;}")
        self.assertIn("bestName", result.code)
        self.assertNotIn("lowName", result.code)

    def test_all_extended_examples_change_and_parse(self):
        from sct_extended_cases import EXTENDED_CASES
        import javalang

        for sid, options, source in EXTENDED_CASES:
            with self.subTest(sid=sid, options=options, source=source):
                result = create_strategy(sid, **options).apply(source)
                self.assertEqual(result.successful, 1, result.rejections)
                javalang.parse.parse("class T{" + result.code + "}")

    def test_cli_constructor_options_reach_the_registered_strategy(self):
        from operate_sct import parse_strategies

        chain = parse_strategies(
            "CL7:2,SD1:1",
            42,
            {"CL7": {"mode": "first_flag"}, "SD1": {"max_distance": 3}},
        )
        self.assertEqual(chain[0][0].mode, "first_flag")
        self.assertEqual(chain[0][1], 2)
        self.assertEqual(chain[1][0].max_distance, 3)

    def test_extraction_preserves_constant_and_narrowing_contexts(self):
        for source in [
            "short m(){return (1+2)*3;}",
            "int m(){byte a=(1+2)*3;return a;}",
            "int m(int a){final int x=(1+2)*3;switch(a){case x:return 1;default:return 2;}}",
        ]:
            result = create_strategy("SS4").apply(source)
            self.assertEqual(result.successful, 0)
            self.assertEqual(result.code, source)

    def test_identity_removal_preserves_promotion(self):
        source = "int m(byte a){return a+0;}"
        self.assertEqual(create_strategy("SE3")(source), source)

    def test_external_constant_reachability_needs_context(self):
        for sid, source in [
            ("CL7", "int m(){do{}while(FLAG);}"),
            ("CL8", "int m(){while(FLAG){}}"),
        ]:
            result = create_strategy(sid).apply(source)
            self.assertEqual(result.successful, 0)
            self.assertTrue(
                any(
                    r["reason"] == "external_constant_return_reachability_unknown"
                    for r in result.rejections
                )
            )

    def test_reserved_identifier_is_not_sampled(self):
        from operators.sct_impl.base import TypedSampler

        self.assertFalse(TypedSampler.valid_name("_"))


if __name__ == "__main__":
    unittest.main()
