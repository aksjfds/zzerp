from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from database import SessionLocal
from models.catalog import (
    CatalogProduct,
    CustomerSurfaceTreatment,
    ProductCustomerCode,
    ProductCustomerTreatment,
)
from models.sales import CustomerOrder, CustomerOrderItem
from schemas.sales import (
    CustomerOrderCreate,
    CustomerOrderItemInput,
    CustomerOrderUpdate,
)
from services.master_data import normalize_required


class CustomerOrderService:
    @staticmethod
    def _validate_items(
        session,
        customer_name: str,
        items: list[CustomerOrderItemInput],
    ) -> dict[int, ProductCustomerCode]:
        code_ids = {item.product_customer_code_id for item in items}
        codes = session.query(ProductCustomerCode).filter(
            ProductCustomerCode.id.in_(code_ids),
            ProductCustomerCode.customer_name == customer_name,
            ProductCustomerCode.active.is_(True),
        ).all()
        code_map = {item.id: item for item in codes}
        if len(code_map) != len(code_ids):
            raise ValueError("订单包含不存在、已停用或属于其他客户的客编")
        product_ids = {item.product_id for item in codes}
        published_product_ids = {
            item.id for item in session.query(CatalogProduct).filter(
                CatalogProduct.id.in_(product_ids),
                CatalogProduct.status == "published",
            ).all()
        }
        if published_product_ids != product_ids:
            raise ValueError("客户订单只能选择已发布产品")

        treatment_ids = {item.treatment_id for item in items if item.treatment_id}
        treatments = session.query(CustomerSurfaceTreatment).filter(
            CustomerSurfaceTreatment.id.in_(treatment_ids),
            CustomerSurfaceTreatment.customer_name == customer_name,
            CustomerSurfaceTreatment.active.is_(True),
        ).all()
        if len(treatments) != len(treatment_ids):
            raise ValueError(
                "订单包含不存在、已停用或属于其他客户的表面处理"
            )

        allowed_pairs = {
            (item.product_customer_code_id, item.treatment_id)
            for item in session.query(ProductCustomerTreatment).filter(
                ProductCustomerTreatment.product_customer_code_id.in_(code_ids)
            ).all()
        }
        if any(
            item.treatment_id is not None
            and (item.product_customer_code_id, item.treatment_id) not in allowed_pairs
            for item in items
        ):
            raise ValueError("所选客编未启用该表面处理")

        item_keys = [
            (
                item.product_customer_code_id,
                item.treatment_id,
                item.delivery_date,
            )
            for item in items
        ]
        if len(item_keys) != len(set(item_keys)):
            raise ValueError("相同产品、表面处理和交货日期不能重复列入订单")
        return code_map

    @staticmethod
    def _replace_items(
        session,
        order: CustomerOrder,
        items: list[CustomerOrderItemInput],
        code_map: dict[int, ProductCustomerCode],
    ) -> None:
        session.query(CustomerOrderItem).filter(
            CustomerOrderItem.customer_order_id == order.id,
        ).delete()
        for item in items:
            code = code_map[item.product_customer_code_id]
            session.add(
                CustomerOrderItem(
                    customer_order_id=order.id,
                    customer_name=order.customer_name,
                    product_id=code.product_id,
                    product_customer_code_id=code.id,
                    treatment_id=item.treatment_id,
                    quantity=item.quantity,
                    delivery_date=item.delivery_date,
                )
            )

    @staticmethod
    def _serialize(session, order: CustomerOrder) -> dict:
        items = session.query(CustomerOrderItem).filter(
            CustomerOrderItem.customer_order_id == order.id,
        ).order_by(CustomerOrderItem.id.asc()).all()
        product_ids = {item.product_id for item in items}
        code_ids = {item.product_customer_code_id for item in items}
        treatment_ids = {item.treatment_id for item in items if item.treatment_id}
        products = {
            item.id: item
            for item in session.query(CatalogProduct).filter(
                CatalogProduct.id.in_(product_ids)
            ).all()
        }
        codes = {
            item.id: item
            for item in session.query(ProductCustomerCode).filter(
                ProductCustomerCode.id.in_(code_ids)
            ).all()
        }
        treatments = {
            item.id: item
            for item in session.query(CustomerSurfaceTreatment).filter(
                CustomerSurfaceTreatment.id.in_(treatment_ids)
            ).all()
        }
        return {
            "id": order.id,
            "customer_name": order.customer_name,
            "purchase_order_no": order.purchase_order_no,
            "version_no": order.version_no,
            "previous_version_id": order.previous_version_id,
            "status": order.status,
            "order_date": order.order_date,
            "note": order.note,
            "items": [
                {
                    "id": item.id,
                    "product_id": item.product_id,
                    "factory_code": products[item.product_id].factory_code,
                    "product_name": products[item.product_id].product_name,
                    "product_customer_code_id": item.product_customer_code_id,
                    "customer_product_code": codes[
                        item.product_customer_code_id
                    ].customer_product_code,
                    "treatment_id": item.treatment_id,
                    "treatment_name": (
                        treatments[item.treatment_id].treatment_name
                        if item.treatment_id else None
                    ),
                    "quantity": item.quantity,
                    "delivery_date": item.delivery_date,
                }
                for item in items
            ],
        }

    @classmethod
    def list_orders(
        cls,
        keyword: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        with SessionLocal() as session:
            query = session.query(CustomerOrder)
            if keyword and keyword.strip():
                pattern = f"%{keyword.strip()}%"
                query = query.filter(
                    or_(
                        CustomerOrder.customer_name.ilike(pattern),
                        CustomerOrder.purchase_order_no.ilike(pattern),
                    )
                )
            if status:
                query = query.filter(CustomerOrder.status == status)
            orders = query.order_by(
                CustomerOrder.order_date.desc(),
                CustomerOrder.id.desc(),
            ).all()
            return [cls._serialize(session, item) for item in orders]

    @classmethod
    def get_order(cls, order_id: int) -> dict:
        with SessionLocal() as session:
            order = session.get(CustomerOrder, order_id)
            if order is None:
                raise ValueError("客户订单不存在")
            return cls._serialize(session, order)

    @classmethod
    def create_order(
        cls,
        payload: CustomerOrderCreate,
        created_by: int,
    ) -> dict:
        customer_name = normalize_required(payload.customer_name, "客户名称")
        purchase_order_no = normalize_required(payload.purchase_order_no, "采购订单号")
        with SessionLocal() as session:
            code_map = cls._validate_items(session, customer_name, payload.items)
            if session.query(CustomerOrder.id).filter(
                CustomerOrder.customer_name == customer_name,
                CustomerOrder.purchase_order_no == purchase_order_no,
            ).first():
                raise ValueError("该客户采购订单号已存在，请从原订单创建变更")
            order = CustomerOrder(
                customer_name=customer_name,
                purchase_order_no=purchase_order_no,
                version_no=1,
                status="draft",
                order_date=payload.order_date,
                note=payload.note.strip() if payload.note else None,
                created_by=created_by,
            )
            session.add(order)
            try:
                session.flush()
                cls._replace_items(session, order, payload.items, code_map)
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ValueError("客户订单资料冲突") from exc
            session.refresh(order)
            return cls._serialize(session, order)

    @classmethod
    def update_order(cls, order_id: int, payload: CustomerOrderUpdate) -> dict:
        with SessionLocal() as session:
            order = session.get(CustomerOrder, order_id)
            if order is None:
                raise ValueError("客户订单不存在")
            if order.status != "draft":
                raise ValueError("只有草稿订单允许修改")
            code_map = cls._validate_items(session, order.customer_name, payload.items)
            order.order_date = payload.order_date
            order.note = payload.note.strip() if payload.note else None
            cls._replace_items(session, order, payload.items, code_map)
            session.commit()
            return cls._serialize(session, order)

    @classmethod
    def confirm_order(cls, order_id: int, confirmed_by: int) -> dict:
        with SessionLocal() as session:
            order = session.get(CustomerOrder, order_id)
            if order is None:
                raise ValueError("客户订单不存在")
            if order.status != "draft":
                raise ValueError("只有草稿订单允许确认")
            items = session.query(CustomerOrderItem).filter(
                CustomerOrderItem.customer_order_id == order.id,
            ).all()
            if not items:
                raise ValueError("空客户订单不能确认")
            cls._validate_items(
                session,
                order.customer_name,
                [
                    CustomerOrderItemInput(
                        product_customer_code_id=item.product_customer_code_id,
                        treatment_id=item.treatment_id,
                        quantity=item.quantity,
                        delivery_date=item.delivery_date,
                    )
                    for item in items
                ],
            )
            if order.previous_version_id is not None:
                previous = session.get(CustomerOrder, order.previous_version_id)
                if previous is None or previous.status != "confirmed":
                    raise ValueError("原订单不是已确认状态，不能确认该变更")
                previous.status = "superseded"
                session.flush()
            order.status = "confirmed"
            order.confirmed_by = confirmed_by
            order.confirmed_at = datetime.now()
            session.commit()
            session.refresh(order)
            return cls._serialize(session, order)

    @classmethod
    def create_change(cls, order_id: int, created_by: int) -> dict:
        with SessionLocal() as session:
            source = session.query(CustomerOrder).filter(
                CustomerOrder.id == order_id,
            ).with_for_update().one_or_none()
            if source is None:
                raise ValueError("客户订单不存在")
            if source.status != "confirmed":
                raise ValueError("只有已确认订单允许创建变更")
            existing = session.query(CustomerOrder.id).filter(
                CustomerOrder.previous_version_id == source.id,
                CustomerOrder.status == "draft",
            ).first()
            if existing:
                raise ValueError("该订单已有未完成的变更草稿")
            latest = session.query(CustomerOrder.version_no).filter(
                CustomerOrder.customer_name == source.customer_name,
                CustomerOrder.purchase_order_no == source.purchase_order_no,
            ).order_by(CustomerOrder.version_no.desc()).first()
            changed = CustomerOrder(
                customer_name=source.customer_name,
                purchase_order_no=source.purchase_order_no,
                version_no=latest[0] + 1,
                previous_version_id=source.id,
                status="draft",
                order_date=source.order_date,
                note=source.note,
                created_by=created_by,
            )
            session.add(changed)
            session.flush()
            items = session.query(CustomerOrderItem).filter(
                CustomerOrderItem.customer_order_id == source.id,
            ).all()
            for item in items:
                session.add(
                    CustomerOrderItem(
                        customer_order_id=changed.id,
                        customer_name=changed.customer_name,
                        product_id=item.product_id,
                        product_customer_code_id=item.product_customer_code_id,
                        treatment_id=item.treatment_id,
                        quantity=item.quantity,
                        delivery_date=item.delivery_date,
                    )
                )
            session.commit()
            session.refresh(changed)
            return cls._serialize(session, changed)

    @classmethod
    def cancel_order(cls, order_id: int) -> dict:
        with SessionLocal() as session:
            order = session.get(CustomerOrder, order_id)
            if order is None:
                raise ValueError("客户订单不存在")
            if order.status not in {"draft", "confirmed"}:
                raise ValueError("当前订单状态不允许取消")
            order.status = "cancelled"
            session.commit()
            session.refresh(order)
            return cls._serialize(session, order)
