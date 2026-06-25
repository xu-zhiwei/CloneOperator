"""O2 - Constant Replacement.

Call ``ConstantReplace(...)(code, k=n)`` to replace Java literals with
equivalent numeric, string, or boolean expressions.
"""

from fractions import Fraction
import re

import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from .base_operator import BaseOperator


class ConstantReplace(BaseOperator):
    SUPPORTED_LITERAL_TYPES = {
        "decimal_integer_literal",
        "decimal_floating_point_literal",
        "string_literal",
        "character_literal",
        "true",
        "false",
        "null_literal",
    }
    STRING_SYNONYMS = {
        # Error/failure related (core extension)
        "error": ["failure", "fault", "mistake", "defect", "bug", "issue", "problem"],
        "failure": ["error", "fault", "breakdown", "collapse", "defect", "issue"],
        "fault": ["error", "failure", "flaw", "glitch", "defect", "bug"],
        "mistake": ["error", "fault", "blunder", "error", "oversight"],
        "defect": ["error", "fault", "flaw", "bug", "imperfection"],
        "bug": ["error", "fault", "defect", "glitch", "issue"],
        "issue": ["error", "problem", "bug", "fault", "trouble"],
        "problem": ["issue", "error", "trouble", "difficulty", "challenge"],
        "glitch": ["fault", "bug", "error", "hiccup", "blip"],
        "trouble": ["problem", "issue", "difficulty", "hardship"],
        # Process start/end (core extension)
        "begin": ["start", "initiate", "launch", "commence", "kickoff"],
        "start": ["begin", "initiate", "launch", "commence", "activate"],
        "end": ["finish", "complete", "conclude", "terminate", "cease"],
        "finish": ["end", "complete", "conclude", "finalize", "wrapup"],
        "complete": ["finish", "end", "conclude", "accomplish", "fulfill"],
        "conclude": ["end", "finish", "complete", "terminate", "close"],
        "initiate": ["start", "begin", "launch", "commence"],
        "terminate": ["end", "stop", "conclude", "halt", "cease"],
        # Text/message related (core extension)
        "message": ["msg", "notification", "alert", "prompt", "info", "message"],
        "msg": ["message", "notification", "alert", "prompt"],
        "notification": ["alert", "msg", "message", "reminder"],
        "alert": ["notification", "warning", "prompt", "msg"],
        "info": ["information", "details", "data", "facts"],
        "information": ["info", "details", "data", "facts", "knowledge"],
        # Test/validation related (core extension)
        "test": ["check", "verify", "validate", "confirm", "examine", "inspect"],
        "check": ["test", "verify", "validate", "inspect", "examine", "audit"],
        "verify": ["check", "validate", "confirm", "authenticate", "test"],
        "validate": ["verify", "check", "confirm", "authenticate", "test"],
        "confirm": ["verify", "validate", "check", "affirm", "assert"],
        # Success/failure related (new core scenario)
        "success": ["succeed", "victory", "win", "achievement", "accomplishment"],
        "succeed": ["success", "achieve", "accomplish", "prevail"],
        "successfully": ["correctly", "properly", "effectively", "successfully"],
        "fail": ["failure", "falter", "lose", "miss", "fall short"],
        "failed": ["unsuccessful", "failed", "defeated", "aborted"],
        # Numeric/logic related (new core scenario)
        "true": ["correct", "right", "valid", "accurate"],
        "false": ["incorrect", "wrong", "invalid", "inaccurate"],
        "null": ["empty", "nil", "none", "void"],
        "empty": ["null", "blank", "vacant", "void"],
        "zero": ["nil", "nought", "0"],
        "one": ["single", "sole", "only"],
        # File/path related (new high-frequency scenario)
        "file": ["document", "archive", "folder", "path"],
        "path": ["route", "directory", "file path", "location"],
        "directory": ["folder", "path", "location"],
        "folder": ["directory", "file folder", "path"],
        # Operation/action related (new high-frequency scenario)
        "add": ["insert", "append", "include", "attach"],
        "insert": ["add", "append", "embed", "introduce"],
        "delete": ["remove", "erase", "eliminate", "discard"],
        "remove": ["delete", "erase", "extract", "take out"],
        "update": ["refresh", "modify", "revise", "renew"],
        "modify": ["change", "alter", "adjust", "update"],
        "create": ["make", "generate", "build", "produce"],
        "read": ["load", "retrieve", "access", "fetch"],
        "write": ["save", "store", "record", "log"],
        "save": ["write", "store", "preserve", "keep"],
        "load": ["read", "retrieve", "fetch", "import"],
        "delete": ["remove", "erase", "clear", "discard"],
        "clear": ["erase", "delete", "empty", "reset"],
        # State/mode related (new high-frequency scenario)
        "active": ["enabled", "running", "operational", "live"],
        "enabled": ["active", "on", "operational", "functional"],
        "inactive": ["disabled", "off", "idle", "stopped"],
        "disabled": ["inactive", "off", "deactivated", "non-functional"],
        "running": ["active", "operating", "working", "in progress"],
        "stopped": ["halted", "paused", "terminated", "ended"],
        "idle": ["inactive", "waiting", "unused", "free"],
        # Time/delay related (new high-frequency scenario)
        "time": ["duration", "period", "interval", "moment"],
        "delay": ["wait", "pause", "hold", "lag"],
        "wait": ["delay", "pause", "hold", "await"],
        "timeout": ["time limit", "expiry", "delay", "overtime"],
        "interval": ["period", "gap", "pause", "duration"],
        # Network/connection related (new high-frequency scenario)
        "connect": ["link", "join", "attach", "establish"],
        "disconnect": ["unlink", "detach", "break", "terminate"],
        "connection": ["link", "session", "tie", "association"],
        "server": ["host", "backend", "service", "node"],
        "client": ["user", "frontend", "consumer", "device"],
        # Permission/access related (new high-frequency scenario)
        "access": ["permission", "entry", "right", "entry"],
        "permission": ["access", "right", "authorization", "allowance"],
        "deny": ["refuse", "reject", "block", "forbid"],
        "allow": ["permit", "authorize", "enable", "approve"],
        "authorize": ["allow", "permit", "approve", "validate"],
        # Log/output related (new high-frequency scenario)
        "log": ["record", "document", "write", "trace"],
        "trace": ["log", "track", "monitor", "follow"],
        "debug": ["troubleshoot", "diagnose", "fix", "resolve"],
        "warning": ["alert", "caution", "notice", "reminder"],
        "notice": ["warning", "alert", "notification", "message"],
        # General description (new high-frequency scenario)
        "name": ["label", "title", "identifier", "tag"],
        "value": ["amount", "figure", "number", "data"],
        "data": ["information", "records", "values", "details"],
        "list": ["array", "collection", "set", "sequence"],
        "array": ["list", "collection", "set", "sequence"],
        "key": ["identifier", "code", "password", "token"],
        "password": ["passcode", "pin", "key", "credential"],
        "user": ["client", "customer", "account", "profile"],
        "count": ["number", "total", "quantity", "amount"],
        "total": ["sum", "count", "overall", "entire"],
        # Concurrency/multithreading scenario
        "thread": ["process", "task", "routine", "worker"],
        "process": ["thread", "task", "job", "operation"],
        "task": ["job", "process", "thread", "mission"],
        "lock": ["mutex", "semaphore", "guard", "barrier"],
        "mutex": ["lock", "semaphore", "guard"],
        "sync": ["synchronize", "coordinate", "align"],
        "synchronize": ["sync", "coordinate", "align", "harmonize"],
        "async": ["asynchronous", "non-blocking", "parallel"],
        "asynchronous": ["async", "non-blocking", "parallel"],
        "parallel": ["async", "concurrent", "simultaneous"],
        "concurrent": ["parallel", "simultaneous", "async"],
        "pool": ["group", "batch", "collection", "set"],
        "worker": ["thread", "process", "task", "handler"],
        # Exception/catch scenario
        "exception": ["error", "fault", "abnormality", "irregularity"],
        "catch": ["capture", "handle", "trap", "intercept"],
        "throw": ["raise", "emit", "trigger", "generate"],
        "raise": ["throw", "emit", "trigger", "generate"],
        "handle": ["process", "manage", "deal with", "address"],
        "handler": ["processor", "manager", "resolver", "dealer"],
        # Database scenario
        "db": ["database", "datastore", "repository"],
        "database": ["db", "datastore", "repository", "storage"],
        "table": ["sheet", "relation", "collection"],
        "row": ["record", "entry", "tuple"],
        "column": ["field", "attribute", "property"],
        "query": ["search", "request", "fetch", "retrieve"],
        "execute": ["run", "perform", "invoke", "trigger"],
        "commit": ["submit", "apply", "save", "finalize"],
        "rollback": ["revert", "undo", "cancel", "backtrack"],
        "transaction": ["operation", "process", "task", "batch"],
        "index": ["key", "pointer", "reference", "indicator"],
        # Container/collection scenario
        "map": ["dictionary", "hash", "table", "lookup"],
        "dictionary": ["map", "hash", "table", "lookup"],
        "set": ["collection", "group", "list", "array"],
        "collection": ["list", "set", "array", "group"],
        "queue": ["line", "sequence", "buffer", "pending"],
        "stack": ["pile", "heap", "buffer", "store"],
        "heap": ["stack", "pile", "memory", "storage"],
        "buffer": ["cache", "queue", "temporary", "storage"],
        "cache": ["buffer", "store", "memory", "temporary"],
        # UI/interaction scenario
        "button": ["btn", "control", "widget", "toggle"],
        "btn": ["button", "control", "widget", "toggle"],
        "text": ["label", "content", "string", "message"],
        "label": ["text", "caption", "title", "name"],
        "input": ["entry", "field", "box", "form"],
        "output": ["result", "display", "response", "feedback"],
        "display": ["show", "present", "render", "output"],
        "render": ["display", "draw", "generate", "present"],
        "click": ["tap", "press", "select", "activate"],
        "tap": ["click", "press", "touch", "select"],
        "select": ["choose", "pick", "click", "tap"],
        # Performance/resource scenario
        "memory": ["ram", "storage", "space", "cache"],
        "ram": ["memory", "storage", "space", "cache"],
        "cpu": ["processor", "core", "unit", "engine"],
        "processor": ["cpu", "core", "unit", "engine"],
        "speed": ["rate", "pace", "velocity", "performance"],
        "performance": ["speed", "efficiency", "throughput", "productivity"],
        "efficiency": ["performance", "speed", "productivity", "effectiveness"],
        "resource": ["asset", "capacity", "memory", "cpu"],
        "capacity": ["resource", "limit", "size", "volume"],
        # Encryption/security scenario
        "encrypt": ["encode", "secure", "protect", "lock"],
        "encode": ["encrypt", "convert", "transform", "format"],
        "decrypt": ["decode", "unlock", "extract", "retrieve"],
        "decode": ["decrypt", "convert", "transform", "extract"],
        "hash": ["digest", "encrypt", "code", "signature"],
        "digest": ["hash", "summary", "encrypt", "signature"],
        "token": ["key", "code", "credential", "identifier"],
        "secret": ["password", "key", "token", "credential"],
        "secure": ["safe", "protected", "encrypted", "locked"],
        "safe": ["secure", "protected", "safe", "guarded"],
        # Network request scenario
        "get": ["retrieve", "fetch", "request", "access"],
        "post": ["send", "submit", "upload", "transmit"],
        "put": ["update", "replace", "set", "store"],
        "delete": ["remove", "erase", "delete", "clear"],  # Duplicate with existing, reserve for consistency
        "patch": ["update", "modify", "adjust", "fix"],
        "request": ["query", "call", "fetch", "get"],
        "response": ["reply", "answer", "result", "output"],
        "status": ["state", "condition", "mode", "situation"],
        "code": ["status", "number", "identifier", "token"],
        "header": ["metadata", "attribute", "property", "info"],
        "body": ["content", "data", "payload", "message"],
        "payload": ["body", "content", "data", "message"],
        # File operation detailed scenario
        "open": ["access", "launch", "start", "initiate"],
        "close": ["shutdown", "terminate", "end", "finish"],
        "rename": ["rebrand", "relabel", "change name", "renumber"],
        "copy": ["duplicate", "clone", "replicate", "mirror"],
        "paste": ["insert", "copy", "transfer", "duplicate"],
        "move": ["transfer", "relocate", "shift", "migrate"],
        "migrate": ["move", "transfer", "relocate", "shift"],
        "backup": ["copy", "save", "archive", "duplicate"],
        "restore": ["recover", "retrieve", "rebuild", "reinstate"],
        "archive": ["backup", "store", "save", "preserve"],
        # Log detailed scenario
        "info": ["information", "details", "data", "facts"],  # Duplicate with existing, reserve for consistency
        "debug": ["troubleshoot", "diagnose", "fix", "resolve"],  # Duplicate with existing, reserve for consistency
        "error": ["failure", "fault", "mistake", "defect"],  # Duplicate with existing, reserve for consistency
        "warn": ["warning", "alert", "caution", "notice"],
        "warning": ["alert", "caution", "notice", "reminder"],  # Duplicate with existing, reserve for consistency
        "fatal": ["critical", "severe", "catastrophic", "terminal"],
        "critical": ["fatal", "severe", "urgent", "important"],
        "severe": ["fatal", "critical", "serious", "extreme"],
        "verbose": ["detailed", "comprehensive", "full", "extensive"],
    }

    DEFAULT_OPERATORS = ("+", "-", "*", "/")

    def __init__(
        self,
        token_vocab=None,
        max_numeric_depth=4,
        max_numeric_atoms=12,
        max_string_candidates=32,
    ):
        super().__init__()
        if token_vocab is None:
            self._load_token_vocab()
        else:
            self.token_vocab = set(token_vocab)

        self.max_numeric_depth = max_numeric_depth
        self.max_numeric_atoms = max_numeric_atoms
        self.max_string_candidates = max_string_candidates

        self.last_constants = []
        self.last_recommendations = []

    def __call__(self, code, k=1):
        modified_code = code
        for _ in range(k):
            modified_code = self.operate(modified_code)[0]
        return modified_code

    def operate(self, code):
        input_is_bytes = isinstance(code, (bytes, bytearray))
        code_bytes = bytearray(code if input_is_bytes else code.encode("utf-8"))

        tree = self._parse_code(code_bytes)
        constants = self.identify_constants(tree, code_bytes)
        recommendations = self.recommend_replacements(constants)
        updated_code = self.apply_replacements(code_bytes, recommendations)

        if input_is_bytes:
            return bytes(updated_code), recommendations
        return updated_code.decode("utf-8"), recommendations
    

    def _parse_code(self, code_bytes):
        parser = Parser(Language(tsjava.language()))
        return parser.parse(bytes(code_bytes))

    def identify_constants(self, tree, code_bytes):
        constants = []

        def traverse(node):
            if node.type in self.SUPPORTED_LITERAL_TYPES:
                literal_text = code_bytes[node.start_byte : node.end_byte].decode(
                    "utf-8"
                )
                constants.append(
                    {
                        "type": node.type,
                        "text": literal_text,
                        "start_byte": node.start_byte,
                        "end_byte": node.end_byte,
                        "parent_type": node.parent.type if node.parent else None,
                    }
                )

            for child in node.children:
                traverse(child)

        traverse(tree.root_node)
        self.last_constants = constants
        return constants

    def recommend_replacements(self, constants):
        recommendations = []
        cached_recommendations = {}

        for constant in constants:
            cache_key = (constant["type"], constant["text"], constant["parent_type"])
            if cache_key not in cached_recommendations:
                cached_recommendations[cache_key] = self._recommend_single_replacement(
                    constant
                )

            replacement = cached_recommendations[cache_key]
            if replacement is None:
                continue

            recommendations.append({**constant, "replacement": replacement})

        self.last_recommendations = recommendations
        return recommendations

    def apply_replacements(self, code_bytes, recommendations):
        for item in sorted(
            recommendations, key=lambda value: value["start_byte"], reverse=True
        ):
            code_bytes[item["start_byte"] : item["end_byte"]] = item[
                "replacement"
            ].encode("utf-8")
        return code_bytes

    def _recommend_single_replacement(self, constant):
        literal_type = constant["type"]
        literal_text = constant["text"]

        if literal_type in {
            "decimal_integer_literal",
            "decimal_floating_point_literal",
        }:
            return self._recommend_numeric_replacement(constant)
        if literal_type == "string_literal":
            return self._recommend_string_replacement(literal_text)
        if literal_type == "character_literal":
            return None
        if literal_type == "true":
            return self._recommend_boolean_replacement(True)
        if literal_type == "false":
            return self._recommend_boolean_replacement(False)
        return None

    def _recommend_numeric_replacement(self, constant):
        target_value = self._parse_numeric_literal(constant["text"])
        if target_value is None:
            return None

        atoms = self._build_numeric_atoms(target_value, constant["text"])
        if not atoms:
            return None

        return self._search_numeric_expression(target_value, constant["text"], atoms)

    def _recommend_boolean_replacement(self, value):
        if value:
            return self._pick_first_supported(["!false", "(1 < 2)"])
        return self._pick_first_supported(["!true", "(1 > 2)"])

    def _recommend_string_replacement(self, literal_text):
        match = re.fullmatch(r'"([^"\\]*)"', literal_text)
        if not match:
            return None

        original_text = match.group(1)
        candidates = []

        if re.fullmatch(r"[A-Za-z]+", original_text):
            for synonym in self.STRING_SYNONYMS.get(original_text.lower(), []):
                normalized = self._apply_string_case(original_text, synonym)
                candidates.append((f'"{normalized}"', [normalized]))

        for replaced_text, replaced_words in self._replace_string_substrings(
            original_text
        ):
            candidates.append((f'"{replaced_text}"', replaced_words))

        dedup_candidates = []
        seen = set()
        for candidate, replaced_tokens in candidates:
            if candidate in seen or candidate == literal_text:
                continue
            seen.add(candidate)
            dedup_candidates.append((candidate, replaced_tokens))

        for candidate, replaced_tokens in dedup_candidates:
            if self._is_supported_string_candidate(candidate, replaced_tokens):
                return candidate
        return None

    def _replace_string_substrings(self, original_text):
        matched_keys = []
        for key in sorted(self.STRING_SYNONYMS.keys(), key=len, reverse=True):
            if re.search(re.escape(key), original_text, flags=re.IGNORECASE):
                matched_keys.append(key)

        if not matched_keys:
            return []

        candidates = [(original_text, [])]

        for key in matched_keys:
            pattern = re.compile(re.escape(key), flags=re.IGNORECASE)
            next_candidates = []

            for text, replaced_tokens in candidates:
                next_candidates.append((text, list(replaced_tokens)))

                for synonym in self.STRING_SYNONYMS.get(key, []):
                    current_replacements = []

                    def replace_match(match):
                        matched_text = match.group(0)
                        replacement = self._apply_string_case(matched_text, synonym)
                        if replacement != matched_text:
                            current_replacements.append(replacement)
                        return replacement

                    replaced_text = pattern.sub(replace_match, text)
                    if replaced_text != text:
                        next_candidates.append(
                            (replaced_text, replaced_tokens + current_replacements)
                        )

            dedup = []
            seen_text = set()
            for text, replaced_tokens in next_candidates:
                if text in seen_text:
                    continue
                seen_text.add(text)
                dedup.append((text, replaced_tokens))
                if len(dedup) >= self.max_string_candidates:
                    break

            candidates = dedup

        return [candidate for candidate in candidates if candidate[0] != original_text]

    def _apply_string_case(self, source, target):
        if source.isupper():
            return target.upper()
        if source.istitle():
            return target.title()
        return target

    def _is_supported_string_candidate(self, candidate, replaced_tokens):
        if not self.token_vocab:
            return True

        inner_text = candidate[1:-1]
        if inner_text in self.token_vocab:
            return True

        if not replaced_tokens:
            return False

        for token in replaced_tokens:
            variants = {token, token.lower(), token.upper(), token.title()}
            if not any(variant in self.token_vocab for variant in variants):
                return False

        return True

    def _pick_first_supported(self, candidates, is_string_literal=False):
        for candidate in candidates:
            if candidate is None:
                continue
            if self._is_supported_candidate(
                candidate, is_string_literal=is_string_literal
            ):
                return candidate
        return None

    def _is_supported_candidate(self, candidate, is_string_literal=False):
        if not self.token_vocab:
            return True

        if is_string_literal:
            inner_text = candidate[1:-1]
            return inner_text in self.token_vocab

        for token in self._tokenize_candidate(candidate):
            if token not in self.token_vocab:
                return False
        return True

    def _tokenize_candidate(self, candidate):
        return re.findall(
            r"\d+\.\d+|\d+|[A-Za-z_][A-Za-z_0-9]*|==|!=|<=|>=|&&|\|\||\S", candidate
        )

    def _parse_numeric_literal(self, literal_text):
        match = re.fullmatch(
            r"([0-9][0-9_]*(?:\.[0-9][0-9_]*)?)([lLfFdD]?)", literal_text
        )
        if not match:
            return None

        numeric_body = match.group(1).replace("_", "")
        try:
            return Fraction(numeric_body)
        except ValueError:
            return None

    def _build_numeric_atoms(self, target_value, literal_text):
        atoms = []
        seen_codes = set()

        def add_atom(atom_value, atom_code):
            if atom_code in seen_codes:
                return
            if self.token_vocab and atom_code not in self.token_vocab:
                return
            seen_codes.add(atom_code)
            atoms.append({"value": atom_value, "code": atom_code})

        if self.token_vocab:
            for token in sorted(self.token_vocab):
                token_value = self._parse_numeric_literal(token)
                if token_value is not None:
                    add_atom(token_value, token)
        else:
            for atom_value, atom_code in self._default_numeric_atoms(
                target_value, literal_text
            ):
                add_atom(atom_value, atom_code)

        atoms.sort(
            key=lambda item: (
                self._atom_priority(item, target_value),
                len(item["code"]),
                item["code"],
            )
        )
        return atoms[: self.max_numeric_atoms]

    def _default_numeric_atoms(self, target_value, literal_text):
        atoms = []
        suggestions = {
            Fraction(0),
            Fraction(1),
            Fraction(2),
            Fraction(3),
            Fraction(5),
            Fraction(10),
        }

        suggestions.add(target_value)
        if target_value > 0:
            suggestions.add(target_value / 2)
            suggestions.add(target_value * 2)

        if target_value.denominator == 1:
            integer_value = abs(target_value.numerator)
            if integer_value > 1:
                split_left = integer_value // 2
                split_right = integer_value - split_left
                suggestions.add(Fraction(split_left))
                suggestions.add(Fraction(split_right))

                factor_pair = self._find_integer_factor_pair(integer_value)
                if factor_pair is not None:
                    factor_left, factor_right = factor_pair
                    suggestions.add(Fraction(factor_left))
                    suggestions.add(Fraction(factor_right))

            for digit in str(integer_value):
                suggestions.add(Fraction(int(digit)))
        else:
            suggestions.add(target_value / 2)

        for suggestion in suggestions:
            literal = self._fraction_to_numeric_literal(suggestion)
            if literal is not None:
                atoms.append((suggestion, literal))

        return atoms

    def _find_integer_factor_pair(self, value):
        if value <= 1:
            return None

        factor = int(value**0.5)
        while factor > 1:
            if value % factor == 0:
                return factor, value // factor
            factor -= 1
        return None

    def _fraction_to_numeric_literal(self, value):
        if value.denominator == 1:
            return str(value.numerator)

        denominator = value.denominator
        while denominator % 2 == 0:
            denominator //= 2
        while denominator % 5 == 0:
            denominator //= 5

        if denominator != 1:
            return None

        decimal_text = format(float(value), ".12g")
        if "e" in decimal_text.lower():
            return None
        if "." not in decimal_text:
            decimal_text += ".0"
        return decimal_text

    def _atom_priority(self, atom, target_value):
        return abs(float(atom["value"] - target_value))

    def _search_numeric_expression(self, target_value, original_text, atoms):
        operators = self._available_numeric_operators()
        if not operators:
            return None

        frontier = [atom for atom in atoms]
        visited = {(atom["value"], atom["code"]): 0 for atom in atoms}
        exact_matches = []

        for depth in range(1, self.max_numeric_depth + 1):
            next_frontier = []

            for expression in frontier:
                for atom in atoms:
                    for candidate in self._combine_numeric_expressions(
                        expression, atom, operators
                    ):
                        if candidate["code"] == original_text:
                            continue

                        visit_key = (candidate["value"], candidate["code"])
                        if visit_key in visited and visited[visit_key] <= depth:
                            continue
                        visited[visit_key] = depth

                        if (
                            candidate["value"] == target_value
                            and candidate["code"] != original_text
                        ):
                            exact_matches.append(candidate)

                        next_frontier.append(candidate)

            if exact_matches:
                exact_matches.sort(
                    key=lambda item: self._expression_score(item, original_text)
                )
                return exact_matches[0]["code"]

            next_frontier.sort(
                key=lambda item: self._expression_score(item, original_text)
            )
            frontier = next_frontier[:64]
            if not frontier:
                break

        return None

    def _available_numeric_operators(self, default=True):
        if not self.token_vocab or default:
            return self.DEFAULT_OPERATORS

        if "(" not in self.token_vocab or ")" not in self.token_vocab:
            return tuple()

        return tuple(
            operator
            for operator in self.DEFAULT_OPERATORS
            if operator in self.token_vocab
        )

    def _combine_numeric_expressions(self, left_expr, right_expr, operators):
        candidates = []

        for operator in operators:
            direct = self._build_numeric_candidate(left_expr, operator, right_expr)
            if direct is not None:
                candidates.append(direct)

            if operator in {"-", "/"}:
                reverse = self._build_numeric_candidate(right_expr, operator, left_expr)
                if reverse is not None:
                    candidates.append(reverse)

        return candidates

    def _build_numeric_candidate(self, left_expr, operator, right_expr):
        if operator == "+":
            value = left_expr["value"] + right_expr["value"]
        elif operator == "-":
            value = left_expr["value"] - right_expr["value"]
        elif operator == "*":
            value = left_expr["value"] * right_expr["value"]
        elif operator == "/":
            if right_expr["value"] == 0:
                return None
            value = left_expr["value"] / right_expr["value"]
        else:
            return None

        code = f"({left_expr['code']} {operator} {right_expr['code']})"
        if not self._is_supported_candidate(code):
            return None

        return {"value": value, "code": code}

    def _expression_score(self, expression, original_text):
        code = expression["code"]
        operator_count = sum(
            code.count(operator) for operator in self.DEFAULT_OPERATORS
        )
        same_literal_penalty = original_text in code
        return (same_literal_penalty, operator_count, len(code), code)

    def _load_token_vocab(self):
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained("microsoft/codebert-base")
        self.token_vocab = set(tokenizer.get_vocab().keys())


if __name__ == "__main__":
    import sys
    import os

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    TEST_CODE = """
public class ConstantReplaceTest {

    //// Integer literals: 5, 100, 0, 1
    static int intSmall    = 5;
    static int intLarge    = 100;
    static int intZero     = 0;
    static int intOne      = 1;
    static int intMerge     = 2 + 3;

    // Long literal with L suffix
    static long longVal    = 100L;

    // Floating-point literals
    static double dblVal   = 1.5;
    static double dblVal   = 1.5F;
    static double dblPi    = 3.14;

    // String literals (with synonyms & without synonyms)
    static String strError   = "error";
    static String strBegin   = "begin";
    static String strUnknown = "hello";   // 无同义词，不应替换
    static String strComplex = "error123"; // 无同义词，不应替换
    static String strMerge   = "error begin hello error123";

    // Boolean literals
    static boolean boolTrue  = true;
    static boolean boolFalse = false;

    // Character literal (not replaced for now, remains unchanged)
    static char charVal = 'x';

    // null literal (not replaced for now, remains unchanged)
    static Object objNull = null;
}
""".strip()

    def _show(operator, code):
        new_code = operator(code)
        print("\nOriginal:")
        print(code)
        print("\nAfter replacement:")
        print(new_code)
        print("\nDetected constants:")
        for c in operator.last_constants:
            print(f"  {c['type']:40s} {c['text']!r}")
        print("\nApplied replacements:")
        for r in operator.last_recommendations:
            print(f"  {r['text']!r:20s}  =>  {r['replacement']!r}")

    op_free = ConstantReplace()
    _show(op_free, TEST_CODE)
