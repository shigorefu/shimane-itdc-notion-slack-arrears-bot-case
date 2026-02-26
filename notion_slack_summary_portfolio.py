#!/usr/bin/env python3
"""Portfolio version (sanitized) for 島根ITデザインカレッジ.

- No real API keys
- No real webhook URL
- No real database IDs
"""

import json
import os
import sys
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple

import requests

# ===== Replace placeholders when deploying =====
NOTION_TOKEN = ""
SLACK_WEBHOOK_URL = ""
NOTION_API_VERSION = "2022-06-28"

GAKUHI_DB_ID = "YOUR_GAKUHI_DB_ID"
YACHIN_DB_ID = "YOUR_YACHIN_DB_ID"
DEFAULT_DATABASE_IDS = [GAKUHI_DB_ID, YACHIN_DB_ID]

KINGAKU_PROPERTY = "支払い済み金額"
GAKKA_PROPERTY = "学科"
NENSEI_PROPERTY = "年生"
COURSES = ["IT科", "VD科"]
GRADES = ["1", "2"]

DATE_PROPERTY = ""
DATE_FROM = ""
DATE_TO = ""


def get_env(name: str, required: bool = True, default: Optional[str] = None) -> str:
    value = os.getenv(name, default)
    if required and not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value or ""


def notion_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_API_VERSION,
        "Content-Type": "application/json",
    }


def get_database_schema(notion_token: str, database_id: str) -> Dict:
    url = f"https://api.notion.com/v1/databases/{database_id}"
    response = requests.get(url, headers=notion_headers(notion_token), timeout=30)
    response.raise_for_status()
    return response.json().get("properties", {})


def validate_required_properties(
    database_id: str,
    schema: Dict,
    amount_property: str,
    date_property: str,
) -> None:
    required = [amount_property]
    if date_property.strip():
        required.append(date_property.strip())

    missing = [name for name in required if name not in schema]
    if missing:
        available = ", ".join(sorted(schema.keys()))
        raise ValueError(
            f"DB {database_id}: missing properties {missing}. Available properties: {available}"
        )


def extract_number_from_property(prop: dict) -> Optional[Decimal]:
    if not prop:
        return None

    prop_type = prop.get("type")
    if prop_type == "number":
        value = prop.get("number")
        return Decimal(str(value)) if value is not None else None

    if prop_type == "formula":
        formula = prop.get("formula", {})
        if formula.get("type") == "number" and formula.get("number") is not None:
            return Decimal(str(formula.get("number")))
        return None

    if prop_type == "rollup":
        rollup = prop.get("rollup", {})
        if rollup.get("type") == "number" and rollup.get("number") is not None:
            return Decimal(str(rollup.get("number")))
        return None

    return None


def extract_text_from_property(prop: dict) -> str:
    if not prop:
        return ""

    prop_type = prop.get("type")
    if prop_type == "select":
        option = prop.get("select")
        return option.get("name", "").strip() if option else ""

    if prop_type == "status":
        option = prop.get("status")
        return option.get("name", "").strip() if option else ""

    if prop_type in ("rich_text", "title"):
        texts = prop.get(prop_type, [])
        parts = [item.get("plain_text", "") for item in texts if item.get("plain_text")]
        return "".join(parts).strip()

    if prop_type == "formula":
        formula = prop.get("formula", {})
        if formula.get("type") == "string":
            return str(formula.get("string") or "").strip()
        if formula.get("type") == "number" and formula.get("number") is not None:
            return str(formula.get("number")).strip()

    if prop_type == "rollup":
        rollup = prop.get("rollup", {})
        if rollup.get("type") == "array":
            for item in rollup.get("array", []):
                item_type = item.get("type")
                if item_type == "select" and item.get("select"):
                    return item["select"].get("name", "").strip()
                if item_type == "status" and item.get("status"):
                    return item["status"].get("name", "").strip()
    return ""


def normalize_course(raw: str) -> str:
    value = raw.strip()
    return value if value in COURSES else ""


def normalize_grade(raw: str) -> str:
    value = raw.strip().replace("年", "")
    if value.endswith(".0"):
        value = value[:-2]
    return value if value in GRADES else ""


def build_date_filter(date_property: str, date_from: str, date_to: str) -> Optional[Dict]:
    if not date_property:
        return None

    has_from = bool(date_from.strip())
    has_to = bool(date_to.strip())
    if not has_from and not has_to:
        return None

    date_filter = {"property": date_property, "date": {}}
    if has_from:
        date_filter["date"]["on_or_after"] = date_from.strip()
    if has_to:
        date_filter["date"]["on_or_before"] = date_to.strip()
    return date_filter


def query_database_sum(
    notion_token: str,
    database_id: str,
    property_name: str,
    gakka_property: Optional[str],
    nensei_property: Optional[str],
    date_filter: Optional[Dict] = None,
) -> Tuple[Decimal, int, int, Dict[str, Decimal], int]:
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    headers = notion_headers(notion_token)

    total = Decimal("0")
    rows_seen = 0
    rows_with_value = 0
    rows_with_breakdown = 0
    breakdown = {f"{course}{grade}年": Decimal("0") for grade in GRADES for course in COURSES}

    has_more = True
    next_cursor = None
    while has_more:
        payload = {"page_size": 100}
        if date_filter:
            payload["filter"] = date_filter
        if next_cursor:
            payload["start_cursor"] = next_cursor

        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()

        for row in data.get("results", []):
            rows_seen += 1
            props = row.get("properties", {})
            value = extract_number_from_property(props.get(property_name))
            if value is None:
                continue

            total += value
            rows_with_value += 1

            if gakka_property and nensei_property:
                course = normalize_course(extract_text_from_property(props.get(gakka_property)))
                grade = normalize_grade(extract_text_from_property(props.get(nensei_property)))
                if course and grade:
                    breakdown[f"{course}{grade}年"] += value
                    rows_with_breakdown += 1

        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")

    return total, rows_seen, rows_with_value, breakdown, rows_with_breakdown


def format_decimal(value: Decimal) -> str:
    normalized = value.quantize(Decimal("1"))
    return f"{normalized:,.0f}"


def notion_db_url(database_id: str) -> str:
    return f"https://www.notion.so/{database_id.replace('-', '')}"


def format_breakdown_lines(breakdown: Dict[str, Decimal]) -> List[str]:
    return [
        f"IT科1年: ¥{format_decimal(breakdown['IT科1年'])}",
        f"VD科1年: ¥{format_decimal(breakdown['VD科1年'])}",
        f"IT科2年: ¥{format_decimal(breakdown['IT科2年'])}",
        f"VD科2年: ¥{format_decimal(breakdown['VD科2年'])}",
    ]


def build_report(per_db: List[Tuple[str, Decimal, int, int, Dict[str, Decimal], int, List[str]]]) -> str:
    by_db = {db_id: (db_total, db_breakdown) for db_id, db_total, _, _, db_breakdown, _, _ in per_db}
    zero_breakdown = {f"{course}{grade}年": Decimal("0") for grade in GRADES for course in COURSES}

    gakuhi_total, gakuhi_breakdown = by_db.get(GAKUHI_DB_ID, (Decimal("0"), dict(zero_breakdown)))
    yachin_total, yachin_breakdown = by_db.get(YACHIN_DB_ID, (Decimal("0"), dict(zero_breakdown)))
    grand_total = gakuhi_total + yachin_total

    lines = [
        "おはようございます。",
        "今週分のR8年前期・学費と家賃滞納額のご報告をいたします。",
        "",
        f"*<{notion_db_url(GAKUHI_DB_ID)}|学費>*",
        "━━━━━━━━━━━━━━",
    ]
    lines.extend(format_breakdown_lines(gakuhi_breakdown))
    lines.extend(
        [
            f"*【学費 合計】* *¥{format_decimal(gakuhi_total)}*",
            "",
            "＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝",
            "",
            f"*<{notion_db_url(YACHIN_DB_ID)}|家賃>*",
            "━━━━━━━━━━━━━━",
        ]
    )
    lines.extend(format_breakdown_lines(yachin_breakdown))
    lines.extend(
        [
            f"*【家賃 合計】* *¥{format_decimal(yachin_total)}*",
            "",
            "＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝",
            "",
            "*【滞納額 総合計】*",
            f"*¥{format_decimal(grand_total)}*",
        ]
    )

    return "\n".join(lines)


def post_to_slack(webhook_url: str, text: str) -> None:
    response = requests.post(webhook_url, json={"text": text}, timeout=20)
    response.raise_for_status()


def parse_database_ids(raw: str) -> List[str]:
    ids = [item.strip() for item in raw.split(",") if item.strip()]
    if not ids:
        raise ValueError("NOTION_DATABASE_IDS must contain at least one database id")
    return ids


def main() -> int:
    try:
        notion_token = get_env("NOTION_TOKEN", required=False, default=NOTION_TOKEN)
        if not notion_token:
            raise ValueError("Set NOTION_TOKEN in file top or environment variable NOTION_TOKEN")

        slack_webhook_url = get_env("SLACK_WEBHOOK_URL", required=False, default=SLACK_WEBHOOK_URL)
        if not slack_webhook_url:
            raise ValueError("Set SLACK_WEBHOOK_URL in file top or environment variable SLACK_WEBHOOK_URL")

        database_ids = parse_database_ids(
            get_env("NOTION_DATABASE_IDS", required=False, default=",".join(DEFAULT_DATABASE_IDS))
        )
        property_name = get_env("NOTION_SUM_PROPERTY", required=False, default=KINGAKU_PROPERTY)

        date_property = get_env("NOTION_DATE_PROPERTY", required=False, default=DATE_PROPERTY)
        date_from = get_env("NOTION_DATE_FROM", required=False, default=DATE_FROM)
        date_to = get_env("NOTION_DATE_TO", required=False, default=DATE_TO)
        date_filter = build_date_filter(date_property, date_from, date_to)

        per_db = []
        for db_id in database_ids:
            schema = get_database_schema(notion_token, db_id)
            validate_required_properties(db_id, schema, property_name, date_property)

            missing_breakdown_props = []
            has_gakka = GAKKA_PROPERTY in schema
            has_nensei = NENSEI_PROPERTY in schema
            if not has_gakka:
                missing_breakdown_props.append(GAKKA_PROPERTY)
            if not has_nensei:
                missing_breakdown_props.append(NENSEI_PROPERTY)

            result = query_database_sum(
                notion_token,
                db_id,
                property_name,
                GAKKA_PROPERTY if has_gakka else None,
                NENSEI_PROPERTY if has_nensei else None,
                date_filter,
            )
            db_total, rows_seen, rows_with_value, breakdown, rows_with_breakdown = result
            per_db.append(
                (db_id, db_total, rows_seen, rows_with_value, breakdown, rows_with_breakdown, missing_breakdown_props)
            )

        message = build_report(per_db)
        post_to_slack(slack_webhook_url, message)
        print(message)
        return 0

    except requests.HTTPError as e:
        details = ""
        if e.response is not None:
            try:
                details = f" | response={json.dumps(e.response.json(), ensure_ascii=False)}"
            except ValueError:
                details = f" | response_text={e.response.text}"
        print(f"HTTP error: {e}{details}", file=sys.stderr)
        return 1

    except (ValueError, InvalidOperation) as e:
        print(f"Configuration/data error: {e}", file=sys.stderr)
        return 2

    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 99


if __name__ == "__main__":
    raise SystemExit(main())
