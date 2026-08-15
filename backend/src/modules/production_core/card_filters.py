from collections import defaultdict

from modules.production_core.card_status import dominant_work_status


WORK_STATUS_SORT_RANK = {
    "processing": 5,
    "processing_completed": 4,
    "qc": 3,
    "rework": 2,
    "unprocessed": 1,
    "completed": 0,
}


def filter_and_paginate_cards(
    cards: list[dict],
    page: int,
    page_size: int,
    keyword: str | None,
    workshop_name: str | None,
    work_status: str,
) -> tuple[list[dict], int]:
    filtered = [
        item
        for item in cards
        if matches_filters(
            item,
            keyword,
            workshop_name,
            work_status,
        )
    ]
    filtered.sort(
        key=lambda item: (
            WORK_STATUS_SORT_RANK.get(item["work_status"], 1),
            item["arrived_at"] or "",
            item["card_key"],
        ),
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
    workshop_name: str | None,
    work_status: str,
) -> tuple[list[dict], int]:
    groups: dict[tuple[str, int, str], list[dict]] = defaultdict(list)
    for item in cards:
        if not item["card_key"].startswith("history:"):
            kind = "current"
        elif item["work_status"] != "completed":
            kind = "processing"
        else:
            kind = "history"
        groups[(kind, item["customer_order_item_id"], item["flow_node_id"])].append(item)

    filtered_groups: list[tuple[tuple[str, int, str], list[dict]]] = []
    for group_key, group in groups.items():
        required_sources = {
            material_key
            for item in group
            for material_key in item["assembly_required_material_keys"]
        }
        present_sources = {item["assembly_material_key"] for item in group}
        group_complete = bool(required_sources) and required_sources == present_sources
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
            representative,
            keyword,
            workshop_name,
            work_status,
        ):
            continue
        for item in group:
            item["work_status"] = status
            item["arrived_at"] = arrived_at
            item["assembly_group_complete"] = (
                group_complete if group_key[0] == "current" else True
            )
            item["can_create_work_order"] = (
                item["can_create_work_order"] and group_complete
            )
        filtered_groups.append((group_key, group))

    ordered = sorted(
        filtered_groups,
        key=lambda entry: (
            WORK_STATUS_SORT_RANK.get(
                entry[1][0]["work_status"],
                1,
            ),
            entry[1][0]["arrived_at"] or "",
            entry[0][1],
            entry[0][0],
            entry[0][2],
        ),
        reverse=True,
    )
    total = len(ordered)
    selected = ordered[(page - 1) * page_size:page * page_size]
    return [item for _, group in selected for item in group], total


def matches_filters(
    item: dict,
    keyword: str | None,
    workshop_name: str | None,
    work_status: str,
) -> bool:
    if work_status != "all" and item["work_status"] != work_status:
        return False
    if workshop_name and item["workshop_name"] != workshop_name:
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
    if all(item["work_status"] == "completed" for item in group):
        return "completed"
    return dominant_work_status(
        (item["work_status"] for item in group if item["work_status"] != "completed")
    )
