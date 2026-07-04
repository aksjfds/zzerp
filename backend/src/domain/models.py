from dataclasses import dataclass


@dataclass(frozen=True)
class BomItemCommand:
    id: int | None
    part_name: str
    part_no: str
    pcs: str
    remark: str | None
