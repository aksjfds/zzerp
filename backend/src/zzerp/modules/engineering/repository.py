from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased, selectinload

from zzerp.modules.engineering.contracts import ProcessFlowPayload
from zzerp.modules.engineering.persistence import (
    Product,
    ProductAppearance,
    ProductBom,
    ProductProcessFlow,
)
from zzerp.modules.engineering.routing import synchronize_routes
from zzerp.modules.engineering.rules import BomItemCommand, product_not_found
from zzerp.modules.sales.api import customer_ids_matching_name_query


class EngineeringProductRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_with_bom_counts(
        self,
        offset: int = 0,
        limit: int = 50,
        keyword: str | None = None,
        customer_id: int | None = None,
    ) -> list[tuple[Product, int]]:
        product_page = (
            select(Product)
            .where(
                self._search_condition(keyword),
                Product.customer_id == customer_id if customer_id is not None else True,
            )
            .order_by(Product.updated_at.desc(), Product.id.desc())
            .offset(offset)
            .limit(limit)
            .subquery()
        )
        page_product = aliased(Product, product_page)
        bom_count = (
            select(func.count(ProductBom.id))
            .where(
                ProductBom.product_id == page_product.id,
            )
            .correlate(page_product)
            .scalar_subquery()
        )
        statement = (
            select(page_product, bom_count)
            .options(selectinload(page_product.appearances))
            .order_by(page_product.updated_at.desc(), page_product.id.desc())
        )
        return [(product, count) for product, count in self.session.execute(statement).all()]

    def count(self, keyword: str | None = None, customer_id: int | None = None) -> int:
        return (
            self.session.scalar(
                select(func.count(Product.id)).where(
                    self._search_condition(keyword),
                    Product.customer_id == customer_id if customer_id is not None else True,
                )
            )
            or 0
        )

    def _search_condition(self, keyword: str | None):
        value = (keyword or "").strip()
        if not value:
            return True
        pattern = f"%{value}%"
        customer_ids = customer_ids_matching_name_query(value)
        return (
            Product.product_name.ilike(pattern)
            | Product.factory_code.ilike(pattern)
            | Product.customer_code.ilike(pattern)
            | Product.customer_id.in_(customer_ids)
        )

    def list_options(self, customer_id: int, keyword: str | None) -> list[dict]:
        statement = (
            select(
                Product.id,
                Product.customer_id,
                Product.product_name,
                Product.factory_code,
                ProductAppearance.id.label("appearance_id"),
                ProductAppearance.appearance_name,
            )
            .join(ProductAppearance, ProductAppearance.product_id == Product.id)
            .where(
                Product.customer_id == customer_id,
                or_(
                    self._search_condition(keyword),
                    ProductAppearance.appearance_name.ilike(f"%{(keyword or '').strip()}%"),
                ),
            )
            .order_by(Product.updated_at.desc(), Product.id.desc(), ProductAppearance.id)
            .limit(50)
        )
        return [dict(row) for row in self.session.execute(statement).mappings()]

    def require(self, product_id: int, *, lock: bool = False) -> Product:
        statement = (
            select(Product)
            .options(
                selectinload(Product.bom_items),
                selectinload(Product.process_flows),
                selectinload(Product.appearances),
            )
            .where(Product.id == product_id)
        )
        if lock:
            statement = statement.with_for_update()
        product = self.session.execute(statement).scalar_one_or_none()
        if product is None:
            raise product_not_found()
        return product

    def add(self, product: Product) -> None:
        self.session.add(product)

    def flush(self) -> None:
        self.session.flush()

    def replace_bom(
        self,
        product: Product,
        bom_items: list[BomItemCommand],
    ) -> list[ProductBom]:
        existing_items = product.bom_items[:]
        existing_by_id = {item.id: item for item in existing_items}
        submitted_ids = {item.id for item in bom_items if item.id is not None}

        # Free existing unique part numbers first so two rows can exchange numbers.
        token = uuid4().hex
        for item_id in submitted_ids:
            existing_by_id[item_id].part_no = f"__updating__{token}_{item_id}"
        for item in existing_items:
            if item.id not in submitted_ids:
                product.bom_items.remove(item)
        self.session.flush()

        result: list[ProductBom] = []
        for index, payload in enumerate(bom_items, start=1):
            if payload.id is None:
                item = ProductBom()
                product.bom_items.append(item)
            else:
                item = existing_by_id[payload.id]
            item.part_name = payload.part_name
            item.part_no = payload.part_no
            item.pcs = payload.pcs
            item.remark = payload.remark or None
            item.sort_order = index
            result.append(item)
        self.session.flush()
        return result

    def set_process_flow(self, product: Product, appearance_id: int, flow_json: dict) -> None:
        payload = ProcessFlowPayload.model_validate(flow_json)
        drawing = payload.model_dump(exclude_none=True)
        process_flow = self._process_flow_for_update(product, appearance_id)
        if process_flow is None:
            process_flow = ProductProcessFlow(appearance_id=appearance_id, flow_json=drawing)
            product.process_flows.append(process_flow)
            self.session.flush()
        else:
            process_flow.flow_json = drawing
            process_flow.draft_flow_json = None
        synchronize_routes(self.session, product.id, appearance_id, payload)

    def set_process_flow_draft(
        self, product: Product, appearance_id: int, flow_json: dict | None
    ) -> None:
        process_flow = self._process_flow_for_update(product, appearance_id)
        if process_flow is None:
            product.process_flows.append(
                ProductProcessFlow(
                    appearance_id=appearance_id,
                    draft_flow_json=flow_json,
                )
            )
        else:
            process_flow.draft_flow_json = flow_json

    def _process_flow_for_update(
        self,
        product: Product,
        appearance_id: int,
    ) -> ProductProcessFlow | None:
        with self.session.no_autoflush:
            stored = self.session.scalar(
                select(ProductProcessFlow)
                .where(
                    ProductProcessFlow.product_id == product.id,
                    ProductProcessFlow.appearance_id == appearance_id,
                )
                .with_for_update()
            )
        if stored is not None and stored not in product.process_flows:
            product.process_flows.append(stored)
        return stored
