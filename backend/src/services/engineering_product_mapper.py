from models.engineering import Product, ProductBom


def serialize_bom(item: ProductBom) -> dict:
    return {
        "id": item.id,
        "product_id": item.product_id,
        "product_version": item.product_version,
        "part_name": item.part_name,
        "part_no": item.part_no,
        "pcs": item.pcs,
        "remark": item.remark or "",
        "sort_order": item.sort_order,
    }


def serialize_product_summary(product: Product, bom_count: int) -> dict:
    return {
        "id": product.id,
        "version": product.version,
        "revision": product.revision,
        "customer_name": product.customer_name,
        "product_name": product.product_name,
        "factory_code": product.factory_code,
        "customer_code": product.customer_code,
        "bom_count": bom_count,
        "created_at": product.created_at.isoformat(timespec="minutes"),
        "updated_at": product.updated_at.isoformat(timespec="minutes"),
    }


def serialize_product_detail(
    product: Product,
    empty_flow: dict,
    requested_version: int | None = None,
    *,
    base_info_editable: bool = True,
    version_editable: bool = True,
) -> dict:
    version = requested_version or product.version
    bom_items = [item for item in product.bom_items if item.product_version == version]
    process_flow = next(
        (item for item in product.process_flows if item.product_version == version), None
    )
    return {
        "id": product.id,
        "version": version,
        "current_version": product.version,
        "revision": product.revision,
        "base_info_editable": base_info_editable,
        "version_editable": version_editable,
        "customer_name": product.customer_name,
        "product_name": product.product_name,
        "factory_code": product.factory_code,
        "customer_code": product.customer_code,
        "bom_items": [serialize_bom(item) for item in bom_items],
        "process_flow": process_flow.flow_json if process_flow else empty_flow,
        "created_at": product.created_at.isoformat(timespec="minutes"),
        "updated_at": product.updated_at.isoformat(timespec="minutes"),
    }
