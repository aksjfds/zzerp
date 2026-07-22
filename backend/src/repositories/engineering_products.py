from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from models.customer import Customer
from models.engineering import Product, ProductBom, ProductProcessFlow
from domain.models import BomItemCommand


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
        condition = self._search_condition(keyword)
        statement = (
            select(Product, func.count(ProductBom.id))
            .options(selectinload(Product.customer))
            .join(Customer, Customer.id == Product.customer_id)
            .outerjoin(
                ProductBom,
                (ProductBom.product_id == Product.id)
                & (ProductBom.product_version == Product.version),
            )
            .where(
                condition,
                Product.customer_id == customer_id
                if customer_id is not None
                else True,
            )
            .group_by(Product.id)
            .order_by(Product.updated_at.desc(), Product.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return [(product, count) for product, count in self.session.execute(statement).all()]

    def count(self, keyword: str | None = None, customer_id: int | None = None) -> int:
        return self.session.scalar(
            select(func.count(Product.id))
            .join(Customer, Customer.id == Product.customer_id)
            .where(
                self._search_condition(keyword),
                Product.customer_id == customer_id
                if customer_id is not None
                else True,
            )
        ) or 0

    @staticmethod
    def _search_condition(keyword: str | None):
        value = (keyword or "").strip()
        if not value:
            return True
        pattern = f"%{value}%"
        return (
            Customer.customer_name.ilike(pattern)
            | Product.product_name.ilike(pattern)
            | Product.factory_code.ilike(pattern)
            | Product.customer_code.ilike(pattern)
        )

    def get(self, product_id: int) -> Product | None:
        statement = (
            select(Product)
            .options(
                selectinload(Product.bom_items),
                selectinload(Product.process_flows),
                selectinload(Product.versions),
                selectinload(Product.customer),
            )
            .where(Product.id == product_id)
        )
        return self.session.execute(statement).scalar_one_or_none()

    def add(self, product: Product) -> None:
        self.session.add(product)

    def delete(self, product: Product) -> None:
        self.session.delete(product)

    def flush(self) -> None:
        self.session.flush()

    def replace_bom(
        self,
        product: Product,
        product_version: int,
        bom_items: list[BomItemCommand],
    ) -> list[ProductBom]:
        version_items = [
            item for item in product.bom_items if item.product_version == product_version
        ]
        existing_by_id = {item.id: item for item in version_items}
        submitted_ids = {item.id for item in bom_items if item.id is not None}

        # Free existing unique part numbers first so two rows can exchange numbers.
        token = uuid4().hex
        for item_id in submitted_ids:
            existing_by_id[item_id].part_no = f"__updating__{token}_{item_id}"
        for item in version_items:
            if item.id not in submitted_ids:
                product.bom_items.remove(item)
        self.session.flush()

        result: list[ProductBom] = []
        for index, payload in enumerate(bom_items, start=1):
            if payload.id is None:
                item = ProductBom(product_version=product_version)
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

    def set_process_flow(
        self, product: Product, product_version: int, flow_json: dict
    ) -> None:
        process_flow = next(
            (
                item
                for item in product.process_flows
                if item.product_version == product_version
            ),
            None,
        )
        if process_flow is None:
            product.process_flows.append(
                ProductProcessFlow(product_version=product_version, flow_json=flow_json)
            )
        else:
            process_flow.flow_json = flow_json
