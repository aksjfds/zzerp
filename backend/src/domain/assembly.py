def required_material_quantity(output_quantity: int, bom_pcs: int | None) -> int:
    return output_quantity * (bom_pcs or 1)
