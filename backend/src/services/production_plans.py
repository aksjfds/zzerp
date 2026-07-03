from datetime import datetime

from database import SessionLocal
from domain.enums import MaterialType
from models.bom import (
    ProductBomItem,
    ProductBomVersion,
    SemiFinishedVersion,
)
from models.catalog import (
    CatalogProduct,
    CustomerSurfaceTreatment,
    Material,
    ProductCustomerCode,
)
from models.planning import (
    ProductionPlan,
    ProductionPlanChangeLog,
    ProductionPlanMaterial,
    ProductionPlanOrderItem,
)
from models.organization import Department
from models.production import (
    Product as ProductionItem,
    ProductDepartmentStep,
    Record,
    Repository,
    WorkOrder,
)
from models.routing import MaterialRouteStep, MaterialRouteVersion
from models.sales import CustomerOrder, CustomerOrderItem
from schemas.planning import (
    PlanMaterialAdjustment,
    PlanOrderItemInput,
    ProductionPlanCreate,
    ProductionPlanUpdate,
)


class ProductionPlanService:
    @staticmethod
    def _adjustment_map(
        adjustments: list[PlanMaterialAdjustment],
    ) -> dict[tuple[int, int], PlanMaterialAdjustment]:
        result: dict[tuple[int, int], PlanMaterialAdjustment] = {}
        for item in adjustments:
            key = (item.customer_order_item_id, item.material_id)
            if key in result:
                raise ValueError("同一订单明细的物料调整不能重复")
            result[key] = item
        return result

    @classmethod
    def _build_preview(
        cls,
        session,
        customer_order_id: int,
        requested_items: list[PlanOrderItemInput],
        adjustments: list[PlanMaterialAdjustment] | None = None,
        exclude_plan_id: int | None = None,
    ) -> dict:
        order = session.query(CustomerOrder).filter(
            CustomerOrder.id == customer_order_id,
        ).with_for_update().one_or_none()
        if order is None:
            raise ValueError("客户订单不存在")
        if order.status not in {"confirmed", "planned"}:
            raise ValueError("只有已确认或已排产订单可以创建生产计划")

        item_ids = [item.customer_order_item_id for item in requested_items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("同一客户订单明细不能重复选择")
        order_items = session.query(CustomerOrderItem).filter(
            CustomerOrderItem.id.in_(item_ids),
            CustomerOrderItem.customer_order_id == customer_order_id,
        ).all()
        order_item_map = {item.id: item for item in order_items}
        if len(order_item_map) != len(item_ids):
            raise ValueError("所选明细不存在或不属于该客户订单")

        used_query = session.query(ProductionPlanOrderItem).join(
            ProductionPlan,
            ProductionPlan.id == ProductionPlanOrderItem.production_plan_id,
        ).filter(
            ProductionPlanOrderItem.customer_order_item_id.in_(item_ids),
            ProductionPlan.status != "cancelled",
        )
        if exclude_plan_id is not None:
            used_query = used_query.filter(
                ProductionPlanOrderItem.production_plan_id != exclude_plan_id
            )
        if used_query.first() is not None:
            raise ValueError("所选客户订单明细已创建生产计划")

        request_map = {item.customer_order_item_id: item for item in requested_items}
        adjustment_map = cls._adjustment_map(adjustments or [])
        preview_items = []
        valid_adjustment_keys: set[tuple[int, int]] = set()
        for order_item in order_items:
            request = request_map[order_item.id]
            if request.planned_finished_quantity < order_item.quantity:
                raise ValueError("计划成品数量不能少于客户订单数量")
            preview = cls._build_item_preview(
                session,
                order_item,
                request.planned_finished_quantity,
                adjustment_map,
            )
            preview_items.append(preview)
            valid_adjustment_keys.update(
                (order_item.id, material["material_id"])
                for material in preview["materials"]
            )
        unknown_keys = set(adjustment_map) - valid_adjustment_keys
        if unknown_keys:
            raise ValueError("物料调整包含不属于所选订单明细的物料")
        return {
            "customer_order_id": customer_order_id,
            "items": preview_items,
        }

    @staticmethod
    def _build_item_preview(
        session,
        order_item: CustomerOrderItem,
        planned_finished_quantity: int,
        adjustment_map: dict[tuple[int, int], PlanMaterialAdjustment],
    ) -> dict:
        product = session.get(CatalogProduct, order_item.product_id)
        customer_code = session.get(
            ProductCustomerCode,
            order_item.product_customer_code_id,
        )
        treatment = (
            session.get(CustomerSurfaceTreatment, order_item.treatment_id)
            if order_item.treatment_id else None
        )
        bom = session.query(ProductBomVersion).filter(
            ProductBomVersion.product_id == order_item.product_id,
            ProductBomVersion.status == "published",
        ).with_for_update().one_or_none()
        if bom is None:
            raise ValueError(f"产品 {product.factory_code} 尚未发布BOM")
        bom_items = session.query(ProductBomItem).filter(
            ProductBomItem.bom_version_id == bom.id,
        ).all()
        semi_versions = session.query(SemiFinishedVersion).filter(
            SemiFinishedVersion.product_id == order_item.product_id,
            SemiFinishedVersion.status == "published",
        ).order_by(SemiFinishedVersion.id.asc()).with_for_update().all()
        finished = session.query(Material).filter(
            Material.product_id == order_item.product_id,
            Material.material_type == MaterialType.FINISHED.value,
            Material.active.is_(True),
        ).one_or_none()
        if finished is None:
            raise ValueError(f"产品 {product.factory_code} 缺少有效成品物料")

        quantities = {finished.id: planned_finished_quantity}
        semi_version_map = {}
        for item in bom_items:
            quantities[item.material_id] = item.quantity * planned_finished_quantity
        for version in semi_versions:
            quantities[version.semi_finished_material_id] = (
                version.quantity_per_finished * planned_finished_quantity
            )
            semi_version_map[version.semi_finished_material_id] = version.id

        materials = session.query(Material).filter(
            Material.id.in_(quantities),
            Material.active.is_(True),
        ).all()
        material_map = {item.id: item for item in materials}
        if len(material_map) != len(quantities):
            raise ValueError(f"产品 {product.factory_code} 的生产物料已停用或不存在")
        route_versions = session.query(MaterialRouteVersion).filter(
            MaterialRouteVersion.material_id.in_(quantities),
            MaterialRouteVersion.status == "published",
        ).order_by(MaterialRouteVersion.id.asc()).with_for_update().all()
        route_map = {item.material_id: item.id for item in route_versions}

        material_rows = []
        for material_id, theoretical_quantity in quantities.items():
            material = material_map[material_id]
            route_version_id = route_map.get(material_id)
            if (
                material.material_type != MaterialType.PURCHASED.value
                and route_version_id is None
            ):
                raise ValueError(
                    f"物料 {material.material_code} 尚未发布工艺路线"
                )
            adjustment = adjustment_map.get((order_item.id, material_id))
            planned_quantity = (
                adjustment.planned_quantity if adjustment else theoretical_quantity
            )
            reason = adjustment.adjustment_reason.strip() if (
                adjustment and adjustment.adjustment_reason
            ) else None
            if material.material_type == MaterialType.FINISHED.value:
                if planned_quantity != theoretical_quantity:
                    raise ValueError(
                        "成品计划数量必须在订单明细中填写，"
                        "不能作为物料调整"
                    )
                reason = None
            elif planned_quantity != theoretical_quantity and not reason:
                raise ValueError("调整配件或半成品计划数量时必须填写原因")
            elif planned_quantity == theoretical_quantity:
                reason = None
            material_rows.append(
                {
                    "id": None,
                    "customer_order_item_id": order_item.id,
                    "material_id": material.id,
                    "material_code": material.material_code,
                    "material_name": material.material_name,
                    "material_type": material.material_type,
                    "theoretical_quantity": theoretical_quantity,
                    "planned_quantity": planned_quantity,
                    "adjustment_reason": reason,
                    "semi_finished_version_id": semi_version_map.get(material.id),
                    "route_version_id": route_version_id,
                }
            )
        material_rows.sort(key=lambda item: item["material_code"])
        return {
            "id": None,
            "customer_order_item_id": order_item.id,
            "factory_code": product.factory_code,
            "product_name": product.product_name,
            "customer_product_code": customer_code.customer_product_code,
            "treatment_name": treatment.treatment_name if treatment else None,
            "order_required_quantity": order_item.quantity,
            "planned_finished_quantity": planned_finished_quantity,
            "stock_quantity": planned_finished_quantity - order_item.quantity,
            "product_bom_version_id": bom.id,
            "materials": material_rows,
        }

    @classmethod
    def preview(cls, customer_order_id: int, items: list[PlanOrderItemInput]) -> dict:
        with SessionLocal() as session:
            return cls._build_preview(session, customer_order_id, items)

    @classmethod
    def preview_update(cls, plan_id: int, items: list[PlanOrderItemInput]) -> dict:
        with SessionLocal() as session:
            plan = session.get(ProductionPlan, plan_id)
            if plan is None:
                raise ValueError("生产计划不存在")
            if plan.status != "draft":
                raise ValueError("只有草稿生产计划允许重新计算")
            return cls._build_preview(
                session,
                plan.customer_order_id,
                items,
                exclude_plan_id=plan.id,
            )

    @staticmethod
    def _write_plan_rows(session, plan: ProductionPlan, preview: dict) -> None:
        for item in preview["items"]:
            plan_item = ProductionPlanOrderItem(
                production_plan_id=plan.id,
                customer_order_id=plan.customer_order_id,
                customer_order_item_id=item["customer_order_item_id"],
                product_id=session.get(
                    CustomerOrderItem,
                    item["customer_order_item_id"],
                ).product_id,
                order_required_quantity=item["order_required_quantity"],
                planned_finished_quantity=item["planned_finished_quantity"],
                product_bom_version_id=item["product_bom_version_id"],
            )
            session.add(plan_item)
            session.flush()
            for material in item["materials"]:
                session.add(
                    ProductionPlanMaterial(
                        production_plan_order_item_id=plan_item.id,
                        product_id=plan_item.product_id,
                        material_id=material["material_id"],
                        theoretical_quantity=material["theoretical_quantity"],
                        planned_quantity=material["planned_quantity"],
                        adjustment_reason=material["adjustment_reason"],
                        semi_finished_version_id=material[
                            "semi_finished_version_id"
                        ],
                        route_version_id=material["route_version_id"],
                    )
                )

    @staticmethod
    def _snapshot(plan: ProductionPlan, preview: dict) -> dict:
        return {
            "plan_no": plan.plan_no,
            "status": plan.status,
            "start_date": plan.start_date.isoformat(),
            "completion_date": plan.completion_date.isoformat(),
            "items": preview["items"],
        }

    @classmethod
    def create_plan(cls, payload: ProductionPlanCreate, created_by: int) -> dict:
        with SessionLocal() as session:
            preview = cls._build_preview(
                session,
                payload.customer_order_id,
                payload.items,
                payload.material_adjustments,
            )
            plan = ProductionPlan(
                customer_order_id=payload.customer_order_id,
                status="draft",
                start_date=payload.start_date,
                completion_date=payload.completion_date,
                created_by=created_by,
            )
            session.add(plan)
            session.flush()
            cls._write_plan_rows(session, plan, preview)
            order = session.get(CustomerOrder, payload.customer_order_id)
            if order.status == "confirmed":
                order.status = "planned"
            session.flush()
            session.refresh(plan)
            session.add(
                ProductionPlanChangeLog(
                    production_plan_id=plan.id,
                    changed_by=created_by,
                    change_type="created",
                    old_data={},
                    new_data=cls._snapshot(plan, preview),
                )
            )
            session.commit()
            session.refresh(plan)
            return cls._serialize(session, plan)

    @classmethod
    def _stored_preview(cls, session, plan: ProductionPlan) -> dict:
        rows = session.query(ProductionPlanOrderItem).filter(
            ProductionPlanOrderItem.production_plan_id == plan.id,
        ).order_by(ProductionPlanOrderItem.id.asc()).all()
        preview_items = []
        for row in rows:
            order_item = session.get(CustomerOrderItem, row.customer_order_item_id)
            product = session.get(CatalogProduct, row.product_id)
            code = session.get(
                ProductCustomerCode,
                order_item.product_customer_code_id,
            )
            treatment = (
                session.get(CustomerSurfaceTreatment, order_item.treatment_id)
                if order_item.treatment_id else None
            )
            materials = session.query(ProductionPlanMaterial).filter(
                ProductionPlanMaterial.production_plan_order_item_id == row.id,
            ).order_by(ProductionPlanMaterial.id.asc()).all()
            material_map = {
                item.id: item
                for item in session.query(Material).filter(
                    Material.id.in_([item.material_id for item in materials])
                ).all()
            }
            preview_items.append(
                {
                    "id": row.id,
                    "customer_order_item_id": row.customer_order_item_id,
                    "factory_code": product.factory_code,
                    "product_name": product.product_name,
                    "customer_product_code": code.customer_product_code,
                    "treatment_name": treatment.treatment_name if treatment else None,
                    "order_required_quantity": row.order_required_quantity,
                    "planned_finished_quantity": row.planned_finished_quantity,
                    "stock_quantity": row.stock_quantity,
                    "product_bom_version_id": row.product_bom_version_id,
                    "materials": [
                        {
                            "id": item.id,
                            "customer_order_item_id": row.customer_order_item_id,
                            "material_id": item.material_id,
                            "material_code": material_map[item.material_id].material_code,
                            "material_name": material_map[item.material_id].material_name,
                            "material_type": material_map[item.material_id].material_type,
                            "theoretical_quantity": item.theoretical_quantity,
                            "planned_quantity": item.planned_quantity,
                            "adjustment_reason": item.adjustment_reason,
                            "semi_finished_version_id": item.semi_finished_version_id,
                            "route_version_id": item.route_version_id,
                        }
                        for item in materials
                    ],
                }
            )
        return {"customer_order_id": plan.customer_order_id, "items": preview_items}

    @classmethod
    def _serialize(cls, session, plan: ProductionPlan) -> dict:
        order = session.get(CustomerOrder, plan.customer_order_id)
        preview = cls._stored_preview(session, plan)
        return {
            "id": plan.id,
            "plan_no": plan.plan_no,
            "customer_order_id": plan.customer_order_id,
            "customer_name": order.customer_name,
            "purchase_order_no": order.purchase_order_no,
            "status": plan.status,
            "start_date": plan.start_date,
            "completion_date": plan.completion_date,
            "items": preview["items"],
        }

    @classmethod
    def list_plans(cls, status: str | None = None) -> list[dict]:
        with SessionLocal() as session:
            query = session.query(ProductionPlan)
            if status:
                query = query.filter(ProductionPlan.status == status)
            plans = query.order_by(ProductionPlan.id.desc()).all()
            return [cls._serialize(session, item) for item in plans]

    @classmethod
    def update_plan(
        cls,
        plan_id: int,
        payload: ProductionPlanUpdate,
        changed_by: int,
    ) -> dict:
        with SessionLocal() as session:
            plan = session.get(ProductionPlan, plan_id)
            if plan is None:
                raise ValueError("生产计划不存在")
            if plan.status != "draft":
                raise ValueError("只有草稿生产计划允许修改")
            old_preview = cls._stored_preview(session, plan)
            old_snapshot = cls._snapshot(plan, old_preview)
            preview = cls._build_preview(
                session,
                plan.customer_order_id,
                payload.items,
                payload.material_adjustments,
                exclude_plan_id=plan.id,
            )
            old_rows = session.query(ProductionPlanOrderItem).filter(
                ProductionPlanOrderItem.production_plan_id == plan.id,
            ).all()
            old_row_ids = [item.id for item in old_rows]
            session.query(ProductionPlanMaterial).filter(
                ProductionPlanMaterial.production_plan_order_item_id.in_(old_row_ids)
            ).delete(synchronize_session=False)
            session.query(ProductionPlanOrderItem).filter(
                ProductionPlanOrderItem.production_plan_id == plan.id,
            ).delete(synchronize_session=False)
            session.flush()
            plan.start_date = payload.start_date
            plan.completion_date = payload.completion_date
            cls._write_plan_rows(session, plan, preview)
            session.flush()
            session.add(
                ProductionPlanChangeLog(
                    production_plan_id=plan.id,
                    changed_by=changed_by,
                    change_type="draft_updated",
                    old_data=old_snapshot,
                    new_data=cls._snapshot(plan, preview),
                )
            )
            session.commit()
            return cls._serialize(session, plan)

    @classmethod
    def release_plan(cls, plan_id: int, released_by: int) -> dict:
        with SessionLocal() as session:
            plan = session.get(ProductionPlan, plan_id)
            if plan is None:
                raise ValueError("生产计划不存在")
            if plan.status != "draft":
                raise ValueError("只有草稿生产计划允许下达")
            preview = cls._stored_preview(session, plan)
            if not preview["items"]:
                raise ValueError("空生产计划不能下达")
            old_snapshot = cls._snapshot(plan, preview)
            cls._provision_production_items(session, plan)
            plan.status = "released"
            plan.released_by = released_by
            plan.released_at = datetime.now()
            session.flush()
            session.add(
                ProductionPlanChangeLog(
                    production_plan_id=plan.id,
                    changed_by=released_by,
                    change_type="released",
                    old_data=old_snapshot,
                    new_data=cls._snapshot(plan, preview),
                )
            )
            session.commit()
            return cls._serialize(session, plan)

    @staticmethod
    def _provision_production_items(session, plan: ProductionPlan) -> None:
        plan_items = session.query(ProductionPlanOrderItem).filter(
            ProductionPlanOrderItem.production_plan_id == plan.id,
        ).all()
        for plan_item in plan_items:
            materials = session.query(ProductionPlanMaterial).filter(
                ProductionPlanMaterial.production_plan_order_item_id == plan_item.id,
            ).all()
            for planned_material in materials:
                material = session.get(Material, planned_material.material_id)
                if material.material_type == MaterialType.PURCHASED.value:
                    continue
                existing = session.query(ProductionItem.id).filter(
                    ProductionItem.production_plan_material_id == planned_material.id,
                ).first()
                if existing is not None:
                    continue
                route_steps = session.query(MaterialRouteStep).filter(
                    MaterialRouteStep.route_version_id
                    == planned_material.route_version_id,
                    MaterialRouteStep.step_type == "internal",
                ).order_by(MaterialRouteStep.sequence_no.asc()).all()
                department_ids = {step.department_id for step in route_steps}
                departments = {
                    item.id: item.department_code
                    for item in session.query(Department).filter(
                        Department.id.in_(department_ids)
                    ).all()
                }
                department_codes = []
                for step in route_steps:
                    code = departments.get(step.department_id)
                    if code and code not in department_codes:
                        department_codes.append(code)
                if not department_codes:
                    raise ValueError(
                        f"物料 {material.material_code} 缺少内部生产路线"
                    )
                item = ProductionItem(
                    production_plan_material_id=planned_material.id,
                    order_id=(
                        f"{plan.plan_no}-{plan_item.customer_order_item_id}"
                    ),
                    zz_code=material.material_code,
                    product_name=material.material_name,
                    delivery_date=plan.completion_date,
                )
                session.add(item)
                session.flush()
                for sequence_no, department_code in enumerate(
                    department_codes,
                    start=1,
                ):
                    session.add(
                        ProductDepartmentStep(
                            product_id=item.id,
                            sequence_no=sequence_no,
                            department=department_code,
                        )
                    )
                first_department = department_codes[0]
                session.add(
                    Repository(
                        department=first_department,
                        product_id=item.id,
                        quantity=planned_material.planned_quantity,
                    )
                )
                session.add(
                    Record(
                        product_id=item.id,
                        from_repository="in",
                        to_repository=first_department,
                        quantity=planned_material.planned_quantity,
                        note=f"生产计划 {plan.plan_no} 下达",
                    )
                )

    @classmethod
    def cancel_plan(cls, plan_id: int, changed_by: int) -> dict:
        with SessionLocal() as session:
            plan = session.get(ProductionPlan, plan_id)
            if plan is None:
                raise ValueError("生产计划不存在")
            if plan.status not in {"draft", "released"}:
                raise ValueError("当前生产计划状态不允许取消")
            preview = cls._stored_preview(session, plan)
            old_snapshot = cls._snapshot(plan, preview)
            if plan.status == "released":
                cls._remove_unstarted_production_items(session, plan)
            plan.status = "cancelled"
            session.flush()
            session.add(
                ProductionPlanChangeLog(
                    production_plan_id=plan.id,
                    changed_by=changed_by,
                    change_type="cancelled",
                    old_data=old_snapshot,
                    new_data=cls._snapshot(plan, preview),
                )
            )
            session.commit()
            return cls._serialize(session, plan)

    @staticmethod
    def _remove_unstarted_production_items(
        session,
        plan: ProductionPlan,
    ) -> None:
        plan_item_ids = [
            item.id
            for item in session.query(ProductionPlanOrderItem.id).filter(
                ProductionPlanOrderItem.production_plan_id == plan.id,
            ).all()
        ]
        material_ids = [
            item.id
            for item in session.query(ProductionPlanMaterial.id).filter(
                ProductionPlanMaterial.production_plan_order_item_id.in_(
                    plan_item_ids
                )
            ).all()
        ]
        production_items = session.query(ProductionItem).filter(
            ProductionItem.production_plan_material_id.in_(material_ids)
        ).all()
        production_item_ids = [item.id for item in production_items]
        if session.query(WorkOrder.id).filter(
            WorkOrder.product_id.in_(production_item_ids)
        ).first() is not None:
            raise ValueError("生产计划已有现场工单，不能取消")
        for item in production_items:
            session.delete(item)
        session.flush()
