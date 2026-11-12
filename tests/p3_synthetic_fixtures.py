"""Original synthetic examples for P3 interface tests; not study examples."""

from __future__ import annotations

from hashlib import sha256


TEXT = {
    "en_initial": "At the Lunar Archive's sound-and-light exhibit, put the amber planet card before the teal comet card.",
    "ar_initial": "في معرض أرشيف القمر للصوت والضوء، ضع بطاقة الكوكب الكهرماني قبل بطاقة المذنب الفيروزي.",
    "en_decisive": "For this display, put the teal comet card before the amber planet card.",
    "ar_decisive": "في هذا العرض، ضع بطاقة المذنب الفيروزي قبل بطاقة الكوكب الكهرماني.",
}

CONDITION_LANGUAGES = {
    "EN-EN": ("en", "en"),
    "AR-AR": ("ar", "ar"),
    "EN-AR": ("en", "ar"),
    "AR-EN": ("ar", "en"),
}


def synthetic_item(condition: str = "EN-EN"):
    from multilingual_judge_pilot.judge_inference import JudgeFacingInput

    initial_language, decisive_language = CONDITION_LANGUAGES[condition]
    return JudgeFacingInput.from_mapping(
        {
            "item_id": f"synthetic-lunar-archive-{condition.lower()}",
            "language_condition": condition,
            "action_turn_index": 2,
            "conversation": [
                {
                    "turn_index": 0,
                    "speaker": "user",
                    "language": initial_language,
                    "content": TEXT[f"{initial_language}_initial"],
                },
                {
                    "turn_index": 1,
                    "speaker": "user",
                    "language": decisive_language,
                    "content": TEXT[f"{decisive_language}_decisive"],
                },
            ],
            "action": {
                "tool_name": "sequence_exhibit_cards",
                "display_id": "lunar-archive-exhibit-17",
                "card_order": ["teal-comet", "amber-planet"],
            },
            "public_tool_schema": {
                "tool_name": "sequence_exhibit_cards",
                "parameters": [
                    {"name": "display_id", "type": "string", "required": True},
                    {"name": "card_order", "type": "array[string]", "required": True},
                ],
            },
        }
    )


def fixture_input_manifest_sha256() -> str:
    return sha256(b"independent synthetic P3 fixture manifest v1").hexdigest()


def english_fixture_translation(text: str) -> str:
    translations = {
        TEXT["ar_initial"]: TEXT["en_initial"],
        TEXT["ar_decisive"]: TEXT["en_decisive"],
    }
    return translations.get(text, text)
