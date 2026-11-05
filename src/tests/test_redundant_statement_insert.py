import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OPERATORS_DIR = PROJECT_ROOT / "src" / "operators"
if str(OPERATORS_DIR) not in sys.path:
    sys.path.append(str(OPERATORS_DIR.parent))

from operators.redundant_statement_insert import RedundantStatementInsert  # noqa: E402


class TestTypedSamplingNoCrossType(unittest.TestCase):
    @staticmethod
    def _run_operator_with_stats(stats_payload: dict) -> str:
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as f:
            json.dump(stats_payload, f, ensure_ascii=False)
            stats_path = f.name

        try:
            op = RedundantStatementInsert(
                insert_ratio=1.0,
                seed=42,
                analyzer_mode="def_only",
                type_sampling="frequency",
                name_sampling="frequency",
                init_sampling="frequency",
                stats_path=stats_path,
                stats_scope="overall",
            )
            source = b"class T { void m() { int base = 0; } }"
            transformed = op(source).decode("utf-8")
            return transformed
        finally:
            Path(stats_path).unlink(missing_ok=True)

    def test_int_type_uses_int_bucket_name_and_initializer(self) -> None:
        stats_payload = {
            "overall": {
                "variable_type_frequency": {"int": 100},
                "variable_name_frequency": {"intOnlyName": 1, "stringOnlyName": 999},
                "variable_init_value_frequency": {"1": 1, '"text"': 999},
                "variable_name_frequency_by_type": {
                    "int": {"intOnlyName": 100},
                    "String": {"stringOnlyName": 100},
                },
                "variable_init_value_frequency_by_type": {
                    "int": {"1": 100},
                    "String": {'"text"': 100},
                },
            },
            "datasets": {},
        }

        transformed = self._run_operator_with_stats(stats_payload)

        self.assertIn("int intOnlyName = 1;", transformed)
        self.assertNotIn("int stringOnlyName", transformed)
        self.assertNotIn('int intOnlyName = "text";', transformed)

    def test_string_type_uses_string_bucket_name_and_initializer(self) -> None:
        stats_payload = {
            "overall": {
                "variable_type_frequency": {"String": 100},
                "variable_name_frequency": {"stringOnlyName": 1, "intOnlyName": 999},
                "variable_init_value_frequency": {'"text"': 1, "1": 999},
                "variable_name_frequency_by_type": {
                    "int": {"intOnlyName": 100},
                    "String": {"stringOnlyName": 100},
                },
                "variable_init_value_frequency_by_type": {
                    "int": {"1": 100},
                    "String": {'"text"': 100},
                },
            },
            "datasets": {},
        }

        transformed = self._run_operator_with_stats(stats_payload)

        self.assertIn('String stringOnlyName = "text";', transformed)
        self.assertNotIn("String intOnlyName", transformed)
        self.assertNotIn("String stringOnlyName = 1;", transformed)


if __name__ == "__main__":
    unittest.main()
