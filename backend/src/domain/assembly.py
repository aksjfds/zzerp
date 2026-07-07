from collections import Counter


def required_material_quantity(output_quantity: int, bom_pcs: int | None) -> int:
    return output_quantity * (bom_pcs or 1)


def matches_assembly_sources(
    expected_source_ids: list[str], selected_source_ids: list[str]
) -> bool:
    return Counter(expected_source_ids) == Counter(selected_source_ids)
