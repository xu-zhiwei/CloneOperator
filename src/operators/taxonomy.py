"""SCT Table 1 structure. Empty cells have no strategy in the stated scope."""
from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyLocation:
    level: str
    target: str
    category: str


TABLE = {
    "word": {
        "identifier": {"reordering": (), "redundancy": (), "replacement": ("WI1",)},
        "constant": {
            "reordering": (),
            "redundancy": ("WC1", "WC2"),
            "replacement": ("WC3", "WC4", "WC5", "WC6", "WC7", "WC8"),
        },
    },
    "statement": {
        "expression": {
            "reordering": ("SE1",),
            "redundancy": ("SE2", "SE3"),
            "replacement": ("SE4", "SE5", "SE6", "SE7", "SE8", "SE9", "SE10"),
        },
        "declaration": {
            "reordering": ("SD1",),
            "redundancy": ("SD2", "SD3"),
            "replacement": ("SD4", "SD5"),
        },
        "ordinary_statement": {
            "reordering": ("SS1",),
            "redundancy": ("SS2", "SS3"),
            "replacement": ("SS4", "SS5"),
        },
    },
    "control": {
        "conditional": {
            "reordering": ("CC1",),
            "redundancy": ("CC2", "CC3"),
            "replacement": ("CC4", "CC5", "CC6", "CC7", "CC8", "CC9", "CC10", "CC11", "CC12", "CC13", "CC14"),
        },
        "loop": {
            "reordering": (),
            "redundancy": ("CL1", "CL2"),
            "replacement": ("CL3", "CL4", "CL5", "CL6", "CL7", "CL8"),
        },
    },
}

LOCATIONS = {
    sid: StrategyLocation(level, target, category)
    for level, targets in TABLE.items()
    for target, categories in targets.items()
    for category, ids in categories.items()
    for sid in ids
}


def strategy_ids(level=None, target=None, category=None):
    """Select strategies by their exact Table 1 coordinates."""
    return tuple(
        sid
        for sid, location in LOCATIONS.items()
        if (level is None or location.level == level)
        and (target is None or location.target == target)
        and (category is None or location.category == category)
    )


@dataclass(frozen=True)
class StrategyRelation:
    family_id: str
    inverse_id: str
    direction: str
    inverse_kind: str = "structural"


PAIRS = (
    ("WC1", "WC2", "constant_neutral_term", "insert", "remove"),
    ("WC3", "WC6", "integer_addition", "decompose", "compose"),
    ("WC5", "WC7", "integer_subtraction", "decompose", "compose"),
    ("WC4", "WC8", "truth_constant_negation", "represent", "reduce"),
    ("SE2", "SE3", "expression_neutral_term", "wrap", "unwrap"),
    ("SE5", "SE7", "unit_update", "expand", "contract"),
    ("SE6", "SE8", "compound_assignment", "expand", "contract"),
    ("SE9", "SE10", "demorgan", "expand", "contract"),
    ("SD2", "SD3", "redundant_declaration", "insert", "remove"),
    ("SD4", "SD5", "declaration_initialization", "split", "merge"),
    ("SS2", "SS3", "redundant_computation", "insert", "remove"),
    ("SS4", "SS5", "computation_extraction", "split", "merge"),
    ("CC2", "CC3", "redundant_branch", "insert", "remove"),
    ("CC4", "CC6", "dispatch_shared_body", "if_to_switch", "switch_to_if"),
    ("CC5", "CC7", "dispatch_cloned_body", "if_to_switch", "switch_to_if"),
    ("CC8", "CC9", "conjunction_structure", "nest", "flatten"),
    ("CC11", "CC12", "conditional_assignment", "ternary_to_if", "if_to_ternary"),
    ("CC13", "CC14", "disjunction_structure", "split", "merge"),
    ("CL1", "CL2", "redundant_loop", "insert", "remove"),
    ("CL3", "CL4", "for_while", "for_to_while", "while_to_for"),
    ("CL5", "CL6", "for_do", "for_to_do", "do_to_for"),
    ("CL7", "CL8", "do_while", "do_to_while", "while_to_do"),
)
RELATIONS = {}
for forward, backward, family, first, second in PAIRS:
    RELATIONS[forward] = StrategyRelation(family, backward, first)
    RELATIONS[backward] = StrategyRelation(family, forward, second)
for sid, family, kind in (
    ("WI1", "identifier_renaming", "inverse_mapping"),
    ("SE1", "operand_exchange", "same_site"),
    ("SE4", "relational_reversal", "same_site"),
    ("SD1", "declaration_exchange", "inverse_permutation"),
    ("SS1", "computation_exchange", "inverse_permutation"),
    ("CC1", "case_permutation", "inverse_permutation"),
    ("CC10", "condition_inversion", "normalized_involution"),
):
    RELATIONS[sid] = StrategyRelation(family, sid, "reversible", kind)


def get_relation(strategy_id):
    """Structural counterpart, not a guarantee of source-exact undo/eligibility."""
    return RELATIONS[strategy_id.upper()]
