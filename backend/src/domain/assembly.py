def required_material_quantity(output_quantity: int, bom_pcs: int | None) -> int:
    return output_quantity * (bom_pcs or 1)


def matches_assembly_sources(
    expected_source_ids: list[str], selected_source_ids: list[str]
) -> bool:
    return set(expected_source_ids) == set(selected_source_ids)
