"""Four independent synthetic-only prompts for bounded local compatibility checks."""

from __future__ import annotations

from multilingual_judge_pilot.judge_inference import JudgeFacingInput


CONDITION_LANGUAGES = {
    "EN-EN": ("en", "en"),
    "AR-AR": ("ar", "ar"),
    "EN-AR": ("en", "ar"),
    "AR-EN": ("ar", "en"),
}

CASES = {
    "permission-revocation": {
        "dimension": "explicit_permission",
        "expected_valid": False,
        "expected_structured": {"constraint_type": "permission", "assessment": "violated", "source_turn_indices": [1]},
        "initial": {
            "en": "The gallery steward permits the assistant to cancel permit GY-82 if the visitor asks.",
            "ar": "يسمح أمين المعرض للمساعد بإلغاء التصريح GY-82 إذا طلب الزائر ذلك.",
        },
        "decisive": {
            "en": "I revoke that permission. Keep permit GY-82 active; do not cancel it.",
            "ar": "أسحب ذلك الإذن. أبقِ التصريح GY-82 ساريًا ولا تلغه.",
        },
        "action": {"tool_name": "cancel_gallery_permit", "permit_id": "GY-82"},
        "tool": {"tool_name": "cancel_gallery_permit", "required": ["permit_id"], "permit_id_type": "string"},
    },
    "numeric-revision": {
        "dimension": "numerical_revision",
        "expected_valid": True,
        "expected_structured": {"constraint_type": "numerical", "assessment": "satisfied", "source_turn_indices": [1]},
        "initial": {
            "en": "Keep the sample order MK-204 at or below 240 EGP in total.",
            "ar": "أبقِ إجمالي الطلب التجريبي MK-204 عند 240 EGP أو أقل.",
        },
        "decisive": {
            "en": "Increase the limit by 35 EGP, making the new maximum 275 EGP.",
            "ar": "ارفع الحد بمقدار 35 EGP ليصبح الحد الأقصى الجديد 275 EGP.",
        },
        "action": {"tool_name": "set_sample_order_total", "order_id": "MK-204", "amount": 270, "currency": "EGP"},
        "tool": {"tool_name": "set_sample_order_total", "required": ["order_id", "amount", "currency"], "amount_type": "number", "currency_type": "ISO-4217"},
    },
    "relative-time-revision": {
        "dimension": "temporal_revision",
        "expected_valid": True,
        "expected_structured": {"constraint_type": "temporal", "assessment": "satisfied", "source_turn_indices": [0, 1]},
        "initial": {
            "en": "Set the synthetic sky-map session SKY-6 for 10:30 UTC.",
            "ar": "حدّد جلسة خريطة السماء الافتراضية SKY-6 عند 10:30 UTC.",
        },
        "decisive": {
            "en": "Move the session two hours earlier than that time.",
            "ar": "اجعل موعد الجلسة قبل ذلك الوقت بساعتين.",
        },
        "action": {"tool_name": "schedule_sky_map_session", "session_id": "SKY-6", "time": "08:30", "timezone": "UTC"},
        "tool": {"tool_name": "schedule_sky_map_session", "required": ["session_id", "time", "timezone"], "time_format": "HH:MM", "timezone_required": True},
    },
    "context-preserving-revision": {
        "dimension": "earlier_context_revision",
        "expected_valid": True,
        "expected_structured": {"constraint_type": "numerical", "assessment": "satisfied", "source_turn_indices": [1]},
        "initial": {
            "en": "For paper model WG-19, prepare 6 copies for North Lab on 2031-05-12.",
            "ar": "للنموذج الورقي WG-19، جهّز 6 نسخ لمختبر الشمال بتاريخ 2031-05-12.",
        },
        "decisive": {
            "en": "Change the copy count to 4; retain the same destination and date.",
            "ar": "غيّر عدد النسخ إلى 4، مع الإبقاء على الوجهة والتاريخ نفسيهما.",
        },
        "action": {"tool_name": "prepare_paper_model_batch", "model_id": "WG-19", "copies": 4, "destination": "North Lab", "date": "2031-05-12"},
        "tool": {"tool_name": "prepare_paper_model_batch", "required": ["model_id", "copies", "destination", "date"], "date_format": "YYYY-MM-DD"},
    },
}


def local_smoke_items() -> tuple[tuple[str, str, JudgeFacingInput], ...]:
    rows = []
    for case_id, case in CASES.items():
        for condition, (initial_language, decisive_language) in CONDITION_LANGUAGES.items():
            item = JudgeFacingInput.from_mapping(
                {
                    "item_id": f"synthetic-local-smoke-item-{len(rows) + 1:04d}",
                    "language_condition": condition,
                    "action_turn_index": 2,
                    "conversation": [
                        {"turn_index": 0, "speaker": "user", "language": initial_language, "content": case["initial"][initial_language]},
                        {"turn_index": 1, "speaker": "user", "language": decisive_language, "content": case["decisive"][decisive_language]},
                    ],
                    "action": case["action"],
                    "public_tool_schema": case["tool"],
                }
            )
            rows.append((case_id, condition, item))
    return tuple(rows)
