from models.engineering import Product, ProductBom


def serialize_bom(item: ProductBom) -> dict:
    return {
        "id": item.id,
        "product_id": item.product_id,
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
        "customer_name": product.customer_name,
        "product_name": product.product_name,
        "factory_code": product.factory_code,
        "customer_code": product.customer_code,
        "bom_count": bom_count,
        "created_at": product.created_at.isoformat(timespec="minutes"),
        "updated_at": product.updated_at.isoformat(timespec="minutes"),
    }


def serialize_product_detail(product: Product, empty_flow: dict) -> dict:
    return {
        "id": product.id,
        "version": product.version,
        "customer_name": product.customer_name,
        "product_name": product.product_name,
        "factory_code": product.factory_code,
        "customer_code": product.customer_code,
        "bom_items": [serialize_bom(item) for item in product.bom_items],
        "process_flow": (
            product.process_flow.flow_json if product.process_flow else empty_flow
        ),
        "created_at": product.created_at.isoformat(timespec="minutes"),
        "updated_at": product.updated_at.isoformat(timespec="minutes"),
    }
