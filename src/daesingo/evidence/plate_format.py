"""Korean plate format consistency check — ADR-EVIDENCE-006.

The rule values live in one versioned data file (`plate_format_rules_kr_v1.json`); this
module only interprets them.  The result is a **review signal**, never a VALID/INVALID
verdict: a value that does not fit any known profile is still the observed value and
evidence keeps it with `needs_review=true`.  Passing the check proves nothing either —
a misread that keeps the shape (`12가3456` read as `12누3456`) passes (PR #91 §4).

Two kinds of finding are kept apart, as in the PR #91 experiment (`classify()` / `notes()`):

- `plate.format.*` — the structure is not explained by any known profile (at most one code,
  the first failed check).
- `plate.consistency.*` — the structure is explained, but the combination is outside the
  notice, the profile comes from observation rather than the notice, or the rule set cannot
  check every part of it.

Either kind makes `review_required` true.  The check runs on a normalized copy (NFC,
whitespace removed — core-user-flow.md §12); callers keep storing the original value.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from .errors import PolicyConfigurationError

ACTIVE_RULE_FILE = "plate_format_rules_kr_v1.json"
OFFICIAL = "OFFICIAL"
OBSERVED_OUTSIDE_NOTICE_SCOPE = "OBSERVED_OUTSIDE_NOTICE_SCOPE"

FORMAT_INCOMPLETE = "plate.format.incomplete"
FORMAT_UNKNOWN_SHAPE = "plate.format.unknown_shape"
FORMAT_REGION_UNKNOWN = "plate.format.region_unknown"
FORMAT_USE_CODE_UNKNOWN = "plate.format.use_code_unknown"
FORMAT_HEAD_OUT_OF_RANGE = "plate.format.head_out_of_range"
FORMAT_SERIAL_OUT_OF_RANGE = "plate.format.serial_out_of_range"
CONSISTENCY_PARTIAL_COVERAGE = "plate.consistency.partial_coverage"
"""Product addition over PR #91: ADR-EVIDENCE-006 §4-7 sends profiles the rule set cannot
fully check (motorcycle district, diplomatic) to review instead of passing them silently."""

_PROVENANCES = {OFFICIAL, OBSERVED_OUTSIDE_NOTICE_SCOPE}
_GROUP_CHECKS = (  # fixed order: the first failure is the one reported (PR #91 parity)
    ("region", FORMAT_REGION_UNKNOWN),
    ("use", FORMAT_USE_CODE_UNKNOWN),
    ("head", FORMAT_HEAD_OUT_OF_RANGE),
    ("serial", FORMAT_SERIAL_OUT_OF_RANGE),
)
_CONDITION_KEYS = {"use_in", "class_in", "class_not_in", "serial_below"}
_SELECT_KEYS = {"use_in", "prefix_in"}


@dataclass(frozen=True)
class PlateFormatAssessment:
    """Outcome of one consistency check.

    `shape` is the profile family whose structure the value was matched against (None when no
    family fits).  `matched_profile` is set only when the structure is fully explained.
    """

    rule_ref: str
    normalized: str
    shape: str | None
    matched_profile: str | None
    provenance: str | None
    reason_codes: tuple[str, ...]

    @property
    def review_required(self) -> bool:
        return bool(self.reason_codes)


def _fail(message: str) -> None:
    raise PolicyConfigurationError(f"plate format rules: {message}")


@dataclass(frozen=True)
class _Profile:
    id: str
    provenance: str
    pattern: re.Pattern[str]
    checks: dict[str, Any]
    select_when: dict[str, str]
    variants: tuple[tuple[str, str | None], ...]
    consistency: tuple[tuple[str, dict[str, Any]], ...]
    complete: bool


@dataclass(frozen=True)
class _RuleSet:
    rule_ref: str
    strip: re.Pattern[str]
    sets: dict[str, frozenset[str]]
    bands: dict[str, tuple[tuple[int, int, str], ...]]
    profiles: tuple[_Profile, ...]


def _symbol_sets(raw: Any) -> dict[str, frozenset[str]]:
    if not isinstance(raw, dict) or not raw:
        _fail("symbol_sets must be a non-empty object")
    sets: dict[str, frozenset[str]] = {}
    for name, entry in raw.items():
        if not isinstance(entry, dict) or entry.get("provenance") not in _PROVENANCES:
            _fail(f"symbol set {name} needs a known provenance")
        symbols = entry.get("symbols")
        if not isinstance(symbols, list) or not symbols or not all(isinstance(s, str) and s for s in symbols):
            _fail(f"symbol set {name} must list symbols")
        if len(set(symbols)) != len(symbols):
            _fail(f"symbol set {name} has duplicates")
        sets[name] = frozenset(symbols)
    return sets


def _bands(raw: Any) -> dict[str, tuple[tuple[int, int, str], ...]]:
    if not isinstance(raw, dict) or not raw:
        _fail("class_bands must be a non-empty object")
    tables: dict[str, tuple[tuple[int, int, str], ...]] = {}
    for name, entry in raw.items():
        if not isinstance(entry, dict) or entry.get("provenance") not in _PROVENANCES:
            _fail(f"band table {name} needs a known provenance")
        rows = []
        previous = None
        for band in entry.get("bands") or []:
            low, high, vehicle_class = band.get("from"), band.get("to"), band.get("vehicle_class")
            if not (isinstance(low, int) and isinstance(high, int) and low <= high and isinstance(vehicle_class, str)):
                _fail(f"band table {name} has a malformed band")
            if previous is not None and low <= previous:
                _fail(f"band table {name} must be ascending without overlap")
            previous = high
            rows.append((low, high, vehicle_class))
        if not rows:
            _fail(f"band table {name} is empty")
        tables[name] = tuple(rows)
    return tables


def _condition(raw: Any, allowed: set[str], sets: dict[str, frozenset[str]], where: str) -> dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict) or not raw or set(raw) - allowed:
        _fail(f"{where} has an unsupported condition")
    for key in ("use_in", "prefix_in"):
        if key in raw and raw[key] not in sets:
            _fail(f"{where} references an unknown symbol set")
    if "serial_below" in raw and not isinstance(raw["serial_below"], int):
        _fail(f"{where} serial_below must be an integer")
    return dict(raw)


def _profile(raw: Any, sets: dict[str, frozenset[str]], bands: dict[str, Any], seen: set[str]) -> _Profile:
    if not isinstance(raw, dict):
        _fail("a profile must be an object")
    profile_id = raw.get("id")
    if not isinstance(profile_id, str) or not profile_id or profile_id in seen:
        _fail("profile ids must be unique non-empty strings")
    if raw.get("provenance") not in _PROVENANCES:
        _fail(f"profile {profile_id} needs a known provenance")
    try:
        pattern = re.compile(raw["pattern"])
    except (KeyError, TypeError, re.error):
        _fail(f"profile {profile_id} has an invalid pattern")
    checks = raw.get("checks")
    if not isinstance(checks, dict) or set(checks) - {"region", "use", "head", "serial"}:
        _fail(f"profile {profile_id} has unsupported checks")
    for group in checks:
        if group not in pattern.groupindex:
            _fail(f"profile {profile_id} checks a group its pattern does not capture")
    for group in ("region", "use"):
        if group in checks and (not isinstance(checks[group], list) or any(s not in sets for s in checks[group])):
            _fail(f"profile {profile_id} {group} check must name symbol sets")
    for group in ("head", "serial"):
        rule = checks.get(group)
        if rule is None:
            continue
        if "range" in rule:
            low, high = rule["range"]
            if not (isinstance(low, int) and isinstance(high, int) and low <= high):
                _fail(f"profile {profile_id} {group} range is malformed")
        elif rule.get("bands") not in bands:
            _fail(f"profile {profile_id} {group} references an unknown band table")
    variants = []
    for variant in raw.get("variants") or []:
        if variant.get("use_in") is not None and variant["use_in"] not in sets:
            _fail(f"profile {profile_id} variant references an unknown symbol set")
        variants.append((variant["id"], variant.get("use_in")))
    if variants and variants[-1][1] is not None:
        _fail(f"profile {profile_id} variants must end with a default")
    consistency = tuple(
        (item["code"], _condition(item.get("when"), _CONDITION_KEYS, sets, f"profile {profile_id} consistency"))
        for item in raw.get("consistency") or []
    )
    for code, _ in consistency:
        if not code.startswith("plate.consistency."):
            _fail(f"profile {profile_id} consistency codes must be plate.consistency.*")
    coverage = raw.get("coverage") or {"complete": True}
    if not isinstance(coverage.get("complete"), bool) or (not coverage["complete"] and not coverage.get("reason")):
        _fail(f"profile {profile_id} incomplete coverage needs a reason")
    seen.add(profile_id)
    return _Profile(
        id=profile_id,
        provenance=raw["provenance"],
        pattern=pattern,
        checks=checks,
        select_when=_condition(raw.get("select_when"), _SELECT_KEYS, sets, f"profile {profile_id} select_when"),
        variants=tuple(variants),
        consistency=consistency,
        complete=coverage["complete"],
    )


def load_plate_format_rules(filename: str = ACTIVE_RULE_FILE) -> dict[str, Any]:
    """Read one revision file as data (for tests and audits); evaluation uses the parsed form."""
    try:
        value = json.loads((Path(__file__).parent / filename).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PolicyConfigurationError(f"cannot load plate format rules: {filename}") from exc
    if not isinstance(value, dict):
        _fail("rule data must be an object")
    return value


@lru_cache(maxsize=None)
def _rules(filename: str = ACTIVE_RULE_FILE) -> _RuleSet:
    raw = load_plate_format_rules(filename)
    rule_ref = raw.get("rule_ref")
    if not isinstance(rule_ref, str) or not re.fullmatch(r"plate-format/kr-v\d+", rule_ref):
        _fail("rule_ref must look like plate-format/kr-vN")
    normalization = raw.get("normalization") or {}
    if normalization.get("unicode") != "NFC":
        _fail("normalization must be NFC")
    try:
        strip = re.compile(normalization["strip_pattern"])
    except (KeyError, TypeError, re.error):
        _fail("normalization strip_pattern is invalid")
    sets = _symbol_sets(raw.get("symbol_sets"))
    bands = _bands(raw.get("class_bands"))
    seen: set[str] = set()
    profiles = tuple(_profile(item, sets, bands, seen) for item in raw.get("profiles") or [])
    if not profiles:
        _fail("at least one profile is required")
    return _RuleSet(rule_ref=rule_ref, strip=strip, sets=sets, bands=bands, profiles=profiles)


def plate_format_rule_ref() -> str:
    return _rules().rule_ref


def _vehicle_class(rules: _RuleSet, table: str, head: int) -> str | None:
    for low, high, vehicle_class in rules.bands[table]:
        if low <= head <= high:
            return vehicle_class
    return None


def _in_sets(rules: _RuleSet, value: str, names: list[str]) -> bool:
    return any(value in rules.sets[name] for name in names)


def _holds(rules: _RuleSet, condition: dict[str, Any], groups: dict[str, str], vehicle_class: str | None) -> bool:
    if "use_in" in condition and groups.get("use") not in rules.sets[condition["use_in"]]:
        return False
    if "prefix_in" in condition and groups.get("prefix") not in rules.sets[condition["prefix_in"]]:
        return False
    if "class_in" in condition and vehicle_class not in condition["class_in"]:
        return False
    if "class_not_in" in condition and vehicle_class in condition["class_not_in"]:
        return False
    if "serial_below" in condition and not int(groups["serial"]) < condition["serial_below"]:
        return False
    return True


def _first_failure(rules: _RuleSet, profile: _Profile, groups: dict[str, str]) -> tuple[str | None, str | None]:
    """Return (failed reason code or None, vehicle class from the head band)."""
    vehicle_class = None
    for group, code in _GROUP_CHECKS:
        rule = profile.checks.get(group)
        if rule is None:
            continue
        value = groups[group]
        if group in ("region", "use"):
            if not _in_sets(rules, value, rule):
                return code, None
            continue
        number = int(value)
        if "bands" in rule:
            vehicle_class = _vehicle_class(rules, rule["bands"], number)
            if vehicle_class is None:
                return code, None
        else:
            low, high = rule["range"]
            if not low <= number <= high:
                return code, None
    return None, vehicle_class


def _diagnose(normalized: str) -> str:
    """No profile fits — tell a fragment (`바5215`) from an unknown complete-looking shape."""
    has_head = re.match(r"^[가-힣]{0,6}\d{1,3}", normalized) is not None
    has_use = re.search(r"\d[가-힣]\d", normalized) is not None
    has_serial = re.search(r"\d{4}$", normalized) is not None
    return FORMAT_INCOMPLETE if not (has_head and has_use and has_serial) else FORMAT_UNKNOWN_SHAPE


def normalize_plate_for_check(value: str) -> str:
    """The copy the rules look at. Never store it in place of the observed value."""
    if not isinstance(value, str):
        raise TypeError("a plate value must be a string")
    return _rules().strip.sub("", unicodedata.normalize("NFC", value))


def assess_plate_format(value: str) -> PlateFormatAssessment:
    """Check one plate string against the active rule revision. Pure and deterministic."""
    rules = _rules()
    normalized = normalize_plate_for_check(value)
    for profile in rules.profiles:
        match = profile.pattern.fullmatch(normalized)
        if match is None:
            continue
        groups = {key: text for key, text in match.groupdict().items() if text is not None}
        if profile.select_when and not _holds(rules, profile.select_when, groups, None):
            continue
        failure, vehicle_class = _first_failure(rules, profile, groups)
        if failure is not None:
            return PlateFormatAssessment(rules.rule_ref, normalized, profile.id, None, None, (failure,))
        matched = profile.id
        for variant_id, use_in in profile.variants:
            if use_in is None or groups.get("use") in rules.sets[use_in]:
                matched = variant_id
                break
        codes = [code for code, condition in profile.consistency if _holds(rules, condition, groups, vehicle_class)]
        if not profile.complete:
            codes.append(CONSISTENCY_PARTIAL_COVERAGE)
        return PlateFormatAssessment(rules.rule_ref, normalized, profile.id, matched, profile.provenance, tuple(codes))
    return PlateFormatAssessment(rules.rule_ref, normalized, None, None, None, (_diagnose(normalized),))
