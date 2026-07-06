from domain.errors import DomainViolation
from domain.models import BomItemCommand


def validate_expected_version(actual: int, expected: int) -> None:
    if actual != expected:
        raise DomainViolation(
            "product_version_conflict",
            "产品资料已被其他用户更新，请重新加载后再保存",
            path="expected_version",
            status_code=409,
        )


def validate_bom_identity(
    bom_items: list[BomItemCommand],
    existing_ids: set[int],
) -> set[int]:
    submitted_ids: set[int] = set()
    part_number_indexes: dict[str, int] = {}
    for index, item in enumerate(bom_items):
        if item.part_no in part_number_indexes:
            raise DomainViolation(
                "bom_part_no_conflict",
                f"BOM 配件编号重复：{item.part_no}",
                path=f"bom_items.{index}.part_no",
            )
        part_number_indexes[item.part_no] = index
        if item.id is not None:
            if item.id not in existing_ids or item.id in submitted_ids:
                raise DomainViolation(
                    "invalid_bom_item_id",
                    "BOM 行 ID 无效",
                    path=f"bom_items.{index}.id",
                )
            submitted_ids.add(item.id)
    return submitted_ids
