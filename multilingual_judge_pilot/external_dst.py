"""Input-independent MultiWOZ-style dialogue-state normalization helpers."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Iterable


_EMPTY_VALUES = {"", "none", "not mentioned", "not men", "not"}
_ARABIC_AM = {"ص", "صباحا", "صباحًا"}
_ARABIC_PM = {"م", "مساء", "مساءً"}
_TIME_SLOT_ENDINGS = ("arriveby", "leaveat", "-time", "-book time")
_TIME_RE = re.compile(
    r"^(?P<hour>\d{1,2})(?::|\.)(?P<minute>\d{2})\s*(?P<period>am|pm|a\.m\.|p\.m\.|صباحا|صباحًا|ص|مساء|مساءً|م)?$",
    flags=re.IGNORECASE,
)


def _text(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    value = " ".join(value.split())
    digits: list[str] = []
    for char in value:
        try:
            digits.append(str(unicodedata.decimal(char)))
        except (TypeError, ValueError):
            digits.append(char)
    return "".join(digits)


def _normalized_value(slot: str, value: str) -> str | None:
    text = _text(value).strip()
    if text.casefold() in _EMPTY_VALUES:
        return None
    if slot.casefold().endswith(_TIME_SLOT_ENDINGS):
        match = _TIME_RE.fullmatch(text)
        if match:
            hour = int(match.group("hour"))
            minute = int(match.group("minute"))
            if minute > 59:
                return text.casefold()
            period = (match.group("period") or "").casefold()
            if period in {"pm", "p.m."} | _ARABIC_PM:
                if hour not in range(1, 13):
                    return text.casefold()
                hour = hour % 12 + 12
            elif period in {"am", "a.m."} | _ARABIC_AM:
                if hour not in range(1, 13):
                    return text.casefold()
                hour %= 12
            elif hour > 23:
                return text.casefold()
            return f"{hour:02d}:{minute:02d}"
    return text.casefold()


def normalize_state_mapping(state: Any, slot_inventory: Iterable[str]) -> dict[str, str]:
    """Normalize sparse slot/value mappings; absent values are omitted."""
    inventory = frozenset(slot_inventory)
    if not isinstance(state, dict):
        raise ValueError("invalid_state_mapping")
    output: dict[str, str] = {}
    for slot, value in state.items():
        if not isinstance(slot, str) or slot not in inventory:
            raise ValueError("unknown_slot")
        if not isinstance(value, str):
            raise ValueError("invalid_slot_value")
        normalized = _normalized_value(slot, value)
        if normalized is not None:
            output[slot] = normalized
    return output


def flatten_multiwoz_state(metadata: Any, slot_inventory: Iterable[str]) -> dict[str, str]:
    """Flatten source `metadata` belief states from `semi` and `book` fields.

    The source's `booked` values are system-side transaction results, not user
    constraints, so they are deliberately excluded. Empty and source-normalized
    `none` sentinels are absent; `dontcare` remains an active value.
    """
    inventory = frozenset(slot_inventory)
    if not isinstance(metadata, dict):
        raise ValueError("invalid_gold_metadata")
    flattened: dict[str, str] = {}
    for domain, domain_state in metadata.items():
        if not isinstance(domain, str) or not isinstance(domain_state, dict):
            continue
        for section in ("semi", "book"):
            section_state = domain_state.get(section, {})
            if not isinstance(section_state, dict):
                raise ValueError("invalid_gold_section")
            for field, value in section_state.items():
                if section == "book" and field == "booked":
                    continue
                if not isinstance(field, str) or not isinstance(value, str):
                    raise ValueError("invalid_gold_value")
                normalized = _normalized_value(field, value)
                if normalized is None:
                    continue
                normalized_field = field.lower()
                slot = f"{domain.lower()}-{normalized_field}"
                if section == "book":
                    slot = f"{domain.lower()}-book {normalized_field}"
                if slot not in inventory:
                    raise ValueError("unknown_gold_slot")
                if slot in flattened:
                    raise ValueError("duplicate_gold_slot")
                canonical_value = _normalized_value(slot, value)
                if canonical_value is None:
                    continue
                flattened[slot] = canonical_value
    return flattened


def make_state_output_schema(slot_inventory: Iterable[str]) -> dict[str, Any]:
    """Return a strict sparse JSON Schema using only the public slot inventory."""
    slots = tuple(sorted(set(slot_inventory)))
    if not slots or any(not isinstance(slot, str) or not slot for slot in slots):
        raise ValueError("invalid_slot_inventory")
    return {
        "type": "object",
        "properties": {
            "state": {
                "type": "object",
                "properties": {slot: {"type": "string"} for slot in slots},
                "additionalProperties": False,
            }
        },
        "required": ["state"],
        "additionalProperties": False,
    }


def parse_state_output(raw: Any, slot_inventory: Iterable[str]) -> dict[str, str]:
    """Parse a strict JSON response and normalize its sparse state object."""
    if not isinstance(raw, str) or not raw:
        raise ValueError("missing_response_text")

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result

    try:
        payload = json.loads(
            raw,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError("invalid_json_constant")),
        )
    except ValueError as exc:
        if str(exc) in {"duplicate_json_key", "invalid_json_constant"}:
            raise
        raise ValueError("invalid_json") from None
    if not isinstance(payload, dict) or set(payload) != {"state"}:
        raise ValueError("invalid_response_keys")
    return normalize_state_mapping(payload["state"], slot_inventory)


def score_state_maps(
    gold_state: Any, predicted_state: Any, slot_inventory: Iterable[str]
) -> dict[str, Any]:
    """Return slot exactness, joint goal accuracy, and active slot/value F1."""
    inventory = tuple(sorted(set(slot_inventory)))
    gold = normalize_state_mapping(gold_state, inventory)
    predicted = normalize_state_mapping(predicted_state, inventory)
    slot_correct = sum(gold.get(slot) == predicted.get(slot) for slot in inventory)
    gold_pairs = set(gold.items())
    predicted_pairs = set(predicted.items())
    true_positive = len(gold_pairs & predicted_pairs)
    false_positive = len(predicted_pairs - gold_pairs)
    false_negative = len(gold_pairs - predicted_pairs)
    if predicted_pairs:
        precision = true_positive / len(predicted_pairs)
    else:
        precision = 1.0 if not gold_pairs else 0.0
    if gold_pairs:
        recall = true_positive / len(gold_pairs)
    else:
        recall = 1.0 if not predicted_pairs else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "slot_correct": slot_correct,
        "slot_total": len(inventory),
        "slot_accuracy": slot_correct / len(inventory) if inventory else 0.0,
        "joint_goal_correct": gold == predicted,
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "active_value_precision": precision,
        "active_value_recall": recall,
        "active_value_f1": f1,
    }
