from collections import defaultdict
from datetime import date, datetime, time, timedelta


def filter_and_paginate_cards(
    cards: list[dict],
    page: int,
    page_size: int,
    keyword: str | None,
    arrived_from: date | None,
    arrived_to: date | None,
    work_status: str,
) -> tuple[list[dict], int]:
    filtered = [
        item
        for item in cards
        if matches_filters(item, keyword, arrived_from, arrived_to, work_status)
    ]
    filtered.sort(
        key=lambda item: (item["arrived_at"] or "", item["card_key"]),
        reverse=True,
    )
    total = len(filtered)
    start = (page - 1) * page_size
    return filtered[start:start + page_size], total


def filter_and_paginate_assembly_groups(
    cards: list[dict],
    page: int,
    page_size: int,
    keyword: str | None,
    arrived_from: date | None,
    arrived_to: date | None,
    work_status: str,
) -> tuple[list[dict], int]:
    groups: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for item in cards:
        groups[(item["customer_order_item_id"], item["flow_node_id"])].append(item)

    filtered_groups = []
    for group in groups.values():
        status = _group_status(group)
        arrived_at = max((item["arrived_at"] or "" for item in group), default="") or None
        representative = {
            **group[0],
            "work_status": status,
            "arrived_at": arrived_at,
            "part_name": "-".join(dict.fromkeys(item["part_name"] for item in group)),
            "part_no": " ".join(item["part_no"] for item in group),
        }
        if not matches_filters(
            representative, keyword, arrived_from, arrived_to, work_status
        ):
            continue
        for item in group:
            item["work_status"] = status
            item["arrived_at"] = arrived_at
        filtered_groups.append(group)

    ordered = sorted(
        filtered_groups,
        key=lambda group: group[0]["arrived_at"] or "",
        reverse=True,
    )
    total = len(ordered)
    selected = ordered[(page - 1) * page_size:page * page_size]
    return [item for group in selected for item in group], total


def matches_filters(
    item: dict,
    keyword: str | None,
    arrived_from: date | None,
    arrived_to: date | None,
    work_status: str,
) -> bool:
    if work_status != "all" and item["work_status"] != work_status:
        return False
    arrived_at = datetime.fromisoformat(item["arrived_at"]) if item["arrived_at"] else None
    if arrived_from and (
        arrived_at is None or arrived_at < datetime.combine(arrived_from, time.min)
    ):
        return False
    if arrived_to and (
        arrived_at is None
        or arrived_at >= datetime.combine(arrived_to + timedelta(days=1), time.min)
    ):
        return False
    value = (keyword or "").strip().lower()
    if not value:
        return True
    haystack = " ".join(
        (item["product_name"], item["factory_code"], item["part_name"], item["part_no"])
    ).lower()
    tokens = [
        part
        for part in value.removesuffix("装配体").replace("-", " ").split()
        if part
    ]
    return value in haystack or bool(tokens) and all(token in haystack for token in tokens)


def _group_status(group: list[dict]) -> str:
    if any(item["work_status"] == "processing" for item in group):
        return "processing"
    if all(item["work_status"] == "completed" for item in group):
        return "completed"
    return "unprocessed"
