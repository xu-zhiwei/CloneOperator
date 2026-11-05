"""Contract between SCT Table 1, canonical modules and compatibility imports."""
import ast
import inspect
import re
import importlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from operators import TABLE, LOCATIONS, strategy_ids, REGISTRY


class TaxonomyTests(unittest.TestCase):
    def test_table_cells_match_requested_classification(self):
        expected = {
            ("word", "identifier"): ((), (), ("WI1",)),
            ("word", "constant"): ((), ("WC1", "WC2"), ("WC3", "WC4", "WC5", "WC6", "WC7", "WC8")),
            ("statement", "expression"): (
                ("SE1",),
                ("SE2", "SE3"),
                ("SE4", "SE5", "SE6", "SE7", "SE8", "SE9", "SE10"),
            ),
            ("statement", "declaration"): (("SD1",), ("SD2", "SD3"), ("SD4", "SD5")),
            ("statement", "ordinary_statement"): (
                ("SS1",),
                ("SS2", "SS3"),
                ("SS4", "SS5"),
            ),
            ("control", "conditional"): (
                ("CC1",),
                ("CC2", "CC3"),
                tuple("CC" + str(i) for i in range(4, 15)),
            ),
            ("control", "loop"): (
                (),
                ("CL1", "CL2"),
                tuple("CL" + str(i) for i in range(3, 9)),
            ),
        }
        for (level, target), cells in expected.items():
            for category, ids in zip(
                ("reordering", "redundancy", "replacement"), cells
            ):
                self.assertEqual(TABLE[level][target][category], ids)
                self.assertEqual(strategy_ids(level, target, category), ids)
        self.assertEqual(set(LOCATIONS), set(REGISTRY))
        self.assertEqual(
            sum(
                bool(ids)
                for targets in TABLE.values()
                for categories in targets.values()
                for ids in categories.values()
            ),
            17,
        )

    def test_classes_are_defined_in_their_table_cell(self):
        for sid, cls in REGISTRY.items():
            location = LOCATIONS[sid]
            category = (
                f"operators.java.{location.level}.{location.target}.{location.category}"
            )
            filename = re.sub(r"(?<!^)(?=[A-Z])", "_", cls.__name__).lower()
            module = category + "." + filename
            self.assertEqual(cls.__module__, module)
            self.assertIs(getattr(importlib.import_module(module), cls.__name__), cls)
            self.assertIs(getattr(importlib.import_module(category), cls.__name__), cls)
            source_path = Path(inspect.getsourcefile(cls))
            self.assertEqual(source_path.stem, filename)
            definitions = [
                n
                for n in ast.parse(source_path.read_text()).body
                if isinstance(n, ast.ClassDef)
                and any(
                    isinstance(a, ast.Assign)
                    and any(
                        isinstance(t, ast.Name) and t.id == "strategy_id"
                        for t in a.targets
                    )
                    for a in n.body
                )
            ]
            self.assertEqual([n.name for n in definitions], [cls.__name__])

    def test_each_strategy_has_one_file_and_na_cells_have_no_directory(self):
        root = Path(__file__).resolve().parents[1] / "operators"
        strategy_files = []
        for level, targets in TABLE.items():
            for target, categories in targets.items():
                for category, ids in categories.items():
                    directory = root / "java" / level / target / category
                    self.assertEqual(directory.is_dir(), bool(ids))
                    if ids:
                        files = [
                            p for p in directory.glob("*.py") if p.name != "__init__.py"
                        ]
                        self.assertEqual(len(files), len(ids))
                        strategy_files.extend(files)
        self.assertEqual(len(strategy_files), 51)

    def test_former_target_imports_export_the_same_classes(self):
        targets = {
            "WI": "identifiers",
            "WC": "constants",
            "SE": "expressions",
            "SD": "declarations",
            "SS": "computations",
            "CC": "conditionals",
            "CL": "loops",
        }
        for sid, cls in REGISTRY.items():
            if sid in {"CC4", "CC5", "CC6", "CC7", "CL3", "CL4", "CL5", "CL6"}:
                module = "legacy"
            else:
                module = targets[sid[:2]]
            self.assertIs(
                getattr(
                    importlib.import_module("operators.sct_impl." + module),
                    cls.__name__,
                ),
                cls,
            )


if __name__ == "__main__":
    unittest.main()
