from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from database import SessionLocal
from domain.enums import MaterialType
from models.bom import (
    ProductBomItem,
    ProductBomVersion,
    SemiFinishedInput,
    SemiFinishedVersion,
)
from models.catalog import (
    CatalogProduct,
    CustomerSurfaceTreatment,
    Material,
    ProductCustomerCode,
    ProductCustomerTreatment,
    ProductReleasedSemiNumber,
)
from models.planning import MaterialInventory, ProductionPlanMaterial
from models.routing import MaterialRouteVersion
from schemas.catalog import MaterialCreate, ProductCreate, ProductCustomerCodeCreate
from services.master_data import normalize_required


def _material_data(material: Material) -> dict:
    return {
        "id": material.id,
        "product_id": material.product_id,
        "material_code": material.material_code,
        "material_name": material.material_name,
        "material_type": material.material_type,
        "material_grade": material.material_grade,
        "specification": material.specification,
        "note": material.note,
        "active": material.active,
    }


class CatalogService:
    @staticmethod
    def _validate_treatments(
        session,
        customer_name: str,
        treatment_ids: list[int],
    ) -> list[CustomerSurfaceTreatment]:
        unique_ids = set(treatment_ids)
        if not unique_ids:
            return []
        treatments = session.query(CustomerSurfaceTreatment).filter(
            CustomerSurfaceTreatment.id.in_(unique_ids),
        ).all()
        if len(treatments) != len(unique_ids) or any(
            item.customer_name != customer_name or not item.active
            for item in treatments
        ):
            raise ValueError("表面处理必须属于同一客户且处于启用状态")
        return treatments

    @classmethod
    def _add_customer_code(
        cls,
        session,
        product_id: int,
        payload: ProductCustomerCodeCreate,
    ) -> ProductCustomerCode:
        customer_name = normalize_required(payload.customer_name, "客户名称")
        customer_code = normalize_required(payload.customer_product_code, "客编")
        treatments = cls._validate_treatments(
            session,
            customer_name,
            payload.treatment_ids,
        )
        item = ProductCustomerCode(
            product_id=product_id,
            customer_name=customer_name,
            customer_product_code=customer_code,
            active=True,
        )
        session.add(item)
        session.flush()
        for treatment in treatments:
            session.add(
                ProductCustomerTreatment(
                    product_customer_code_id=item.id,
                    treatment_id=treatment.id,
                    customer_name=customer_name,
                )
            )
        return item

    @staticmethod
    def _next_semi_code(session, product: CatalogProduct) -> str:
        released = session.query(ProductReleasedSemiNumber).filter(
            ProductReleasedSemiNumber.product_id == product.id,
        ).order_by(ProductReleasedSemiNumber.sequence_no.asc()).with_for_update().first()
        if released is not None:
            sequence_no = released.sequence_no
            session.delete(released)
        else:
            sequence_no = product.next_semi_finished_no
            product.next_semi_finished_no += 1
        return f"{product.factory_code}-S{sequence_no:02d}"

    @classmethod
    def _add_material(
        cls,
        session,
        product: CatalogProduct,
        payload: MaterialCreate,
    ) -> Material:
        if payload.material_type == MaterialType.FINISHED:
            raise ValueError("成品物料由系统自动创建")
        if payload.material_type == MaterialType.SEMI_FINISHED:
            material_code = cls._next_semi_code(session, product)
        else:
            material_code = normalize_required(payload.material_code or "", "配件编号")
        material = Material(
            product_id=product.id,
            material_code=material_code,
            material_name=normalize_required(payload.material_name, "物料名称"),
            material_type=payload.material_type.value,
            material_grade=payload.material_grade.strip() if payload.material_grade else None,
            specification=payload.specification.strip() if payload.specification else None,
            note=payload.note.strip() if payload.note else None,
            active=True,
        )
        session.add(material)
        return material

    @staticmethod
    def _serialize_product(session, product: CatalogProduct) -> dict:
        customer_codes = session.query(ProductCustomerCode).filter(
            ProductCustomerCode.product_id == product.id,
        ).order_by(
            ProductCustomerCode.customer_name.asc(),
            ProductCustomerCode.customer_product_code.asc(),
        ).all()
        treatment_rows = session.query(ProductCustomerTreatment).filter(
            ProductCustomerTreatment.product_customer_code_id.in_(
                [item.id for item in customer_codes] or [-1],
            ),
        ).all()
        treatment_map: dict[int, list[int]] = {}
        for row in treatment_rows:
            treatment_map.setdefault(row.product_customer_code_id, []).append(
                row.treatment_id,
            )
        materials = session.query(Material).filter(
            Material.product_id == product.id,
        ).order_by(Material.material_code.asc()).all()
        return {
            "id": product.id,
            "factory_code": product.factory_code,
            "product_name": product.product_name,
            "status": product.status,
            "published_by": product.published_by,
            "published_at": product.published_at,
            "customer_codes": [
                {
                    "id": item.id,
                    "product_id": item.product_id,
                    "customer_name": item.customer_name,
                    "customer_product_code": item.customer_product_code,
                    "active": item.active,
                    "treatment_ids": treatment_map.get(item.id, []),
                }
                for item in customer_codes
            ],
            "materials": [_material_data(item) for item in materials],
        }

    @classmethod
    def list_products(cls, keyword: str | None = None) -> list[dict]:
        with SessionLocal() as session:
            query = session.query(CatalogProduct)
            if keyword and keyword.strip():
                pattern = f"%{keyword.strip()}%"
                query = query.filter(
                    or_(
                        CatalogProduct.factory_code.ilike(pattern),
                        CatalogProduct.product_name.ilike(pattern),
                    )
                )
            products = query.order_by(
                CatalogProduct.factory_code.asc(),
            ).all()
            return [cls._serialize_product(session, item) for item in products]

    @classmethod
    def get_product(cls, product_id: int) -> dict:
        with SessionLocal() as session:
            product = session.get(CatalogProduct, product_id)
            if product is None:
                raise ValueError("产品不存在")
            return cls._serialize_product(session, product)

    @classmethod
    def create_product(cls, payload: ProductCreate, created_by: int) -> dict:
        if not payload.customer_codes:
            raise ValueError("产品至少需要一个客户和客编")
        product = CatalogProduct(
            factory_code=normalize_required(payload.factory_code, "厂编"),
            product_name=normalize_required(payload.product_name, "产品名称"),
            status="draft",
            created_by=created_by,
        )
        with SessionLocal() as session:
            session.add(product)
            try:
                session.flush()
                session.add(
                    Material(
                        product_id=product.id,
                        material_code=product.factory_code,
                        material_name=product.product_name,
                        material_type=MaterialType.FINISHED.value,
                        active=True,
                    )
                )
                for customer_code in payload.customer_codes:
                    cls._add_customer_code(session, product.id, customer_code)
                for material in payload.materials:
                    cls._add_material(session, product, material)
                session.commit()
            except (IntegrityError, ValueError) as exc:
                session.rollback()
                if isinstance(exc, ValueError):
                    raise
                raise ValueError("厂编、客编或配件编号已存在") from exc
            session.refresh(product)
            return cls._serialize_product(session, product)

    @classmethod
    def update_product_name(cls, product_id: int, product_name: str) -> dict:
        with SessionLocal() as session:
            product = session.get(CatalogProduct, product_id)
            if product is None:
                raise ValueError("产品不存在")
            if product.status != "draft":
                raise ValueError("只有草稿产品允许修改产品名称")
            product.product_name = normalize_required(product_name, "产品名称")
            finished = session.query(Material).filter(
                Material.product_id == product.id,
                Material.material_type == MaterialType.FINISHED.value,
            ).one()
            finished.material_name = product.product_name
            session.commit()
            session.refresh(product)
            return cls._serialize_product(session, product)

    @classmethod
    def add_customer_code(
        cls,
        product_id: int,
        payload: ProductCustomerCodeCreate,
    ) -> dict:
        with SessionLocal() as session:
            product = session.get(CatalogProduct, product_id)
            if product is None:
                raise ValueError("产品不存在")
            try:
                cls._add_customer_code(session, product_id, payload)
                session.commit()
            except (IntegrityError, ValueError) as exc:
                session.rollback()
                if isinstance(exc, ValueError):
                    raise
                raise ValueError("客户和客编关系已经存在") from exc
            return cls._serialize_product(session, product)

    @classmethod
    def update_customer_code(
        cls,
        customer_code_id: int,
        treatment_ids: list[int] | None,
        active: bool | None,
    ) -> dict:
        with SessionLocal() as session:
            customer_code = session.get(ProductCustomerCode, customer_code_id)
            if customer_code is None:
                raise ValueError("客户客编不存在")
            if treatment_ids is not None:
                treatments = cls._validate_treatments(
                    session,
                    customer_code.customer_name,
                    treatment_ids,
                )
                session.query(ProductCustomerTreatment).filter(
                    ProductCustomerTreatment.product_customer_code_id
                    == customer_code.id,
                ).delete()
                for treatment in treatments:
                    session.add(
                        ProductCustomerTreatment(
                            product_customer_code_id=customer_code.id,
                            treatment_id=treatment.id,
                            customer_name=customer_code.customer_name,
                        )
                    )
            if active is not None:
                customer_code.active = active
            session.commit()
            product = session.get(CatalogProduct, customer_code.product_id)
            return cls._serialize_product(session, product)

    @classmethod
    def add_material(cls, product_id: int, payload: MaterialCreate) -> dict:
        with SessionLocal() as session:
            product = session.query(CatalogProduct).filter(
                CatalogProduct.id == product_id,
            ).with_for_update().one_or_none()
            if product is None:
                raise ValueError("产品不存在")
            if product.status != "draft":
                raise ValueError("只有草稿产品允许添加物料")
            try:
                material = cls._add_material(session, product, payload)
                session.commit()
            except (IntegrityError, ValueError) as exc:
                session.rollback()
                if isinstance(exc, ValueError):
                    raise
                raise ValueError("物料编号已经存在") from exc
            session.refresh(material)
            return _material_data(material)

    @staticmethod
    def update_material(
        material_id: int,
        material_code: str | None,
        material_type: MaterialType | None,
        material_name: str | None,
        material_grade: str | None,
        specification: str | None,
        note: str | None,
        active: bool | None,
    ) -> dict:
        with SessionLocal() as session:
            material = session.get(Material, material_id)
            if material is None:
                raise ValueError("物料不存在")
            product = session.get(CatalogProduct, material.product_id)
            if product is None or product.status != "draft":
                raise ValueError("只有草稿产品允许修改物料")
            original_code = material.material_code
            original_type = material.material_type
            changes_identity = (
                material_code is not None
                and material_code.strip() != material.material_code
            ) or (
                material_type is not None
                and material_type.value != material.material_type
            )
            if changes_identity:
                if material.material_type == MaterialType.FINISHED.value:
                    raise ValueError("成品物料的类型和编号不能修改")
                if CatalogService._material_is_referenced(session, material.id):
                    raise ValueError(
                        "物料已被BOM、组成、路线、计划或库存引用，"
                        "不能修改类型和编号"
                    )
            if material_code is not None:
                material.material_code = normalize_required(
                    material_code,
                    "物料编号",
                )
            if material_type is not None:
                if material_type == MaterialType.FINISHED:
                    raise ValueError("不能将配件或半成品改为成品")
                if (
                    original_type == MaterialType.SEMI_FINISHED.value
                    and material_type != MaterialType.SEMI_FINISHED
                ):
                    code_parts = original_code.rsplit("-S", 1)
                    if len(code_parts) == 2 and code_parts[1].isdigit():
                        session.add(
                            ProductReleasedSemiNumber(
                                product_id=material.product_id,
                                sequence_no=int(code_parts[1]),
                            )
                        )
                material.material_type = material_type.value
            if material.material_type == MaterialType.FINISHED.value and active is False:
                raise ValueError("成品物料不能单独停用")
            if material_name is not None:
                material.material_name = normalize_required(material_name, "物料名称")
            if material_grade is not None:
                material.material_grade = material_grade.strip() or None
            if specification is not None:
                material.specification = specification.strip() or None
            if note is not None:
                material.note = note.strip() or None
            if active is not None:
                material.active = active
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ValueError("物料编号已经存在") from exc
            session.refresh(material)
            return _material_data(material)

    @classmethod
    def publish_product(cls, product_id: int, published_by: int) -> dict:
        with SessionLocal() as session:
            product = session.query(CatalogProduct).filter(
                CatalogProduct.id == product_id,
            ).with_for_update().one_or_none()
            if product is None:
                raise ValueError("产品不存在")
            if product.status != "draft":
                raise ValueError("只有草稿产品可以发布")

            has_customer_code = session.query(ProductCustomerCode.id).filter(
                ProductCustomerCode.product_id == product_id,
                ProductCustomerCode.active.is_(True),
            ).first()
            if has_customer_code is None:
                raise ValueError("发布前至少需要一个启用的客户客编")

            bom = session.query(ProductBomVersion).filter(
                ProductBomVersion.product_id == product_id,
                ProductBomVersion.status == "published",
            ).one_or_none()
            if bom is None:
                raise ValueError("发布前必须先发布成品BOM")
            if not session.query(ProductBomItem.id).filter(
                ProductBomItem.bom_version_id == bom.id,
            ).first():
                raise ValueError("已发布的成品BOM不能为空")

            active_materials = session.query(Material).filter(
                Material.product_id == product_id,
                Material.active.is_(True),
            ).all()
            semi_ids = {
                item.id for item in active_materials
                if item.material_type == MaterialType.SEMI_FINISHED.value
            }
            published_semi_ids = {
                row[0] for row in session.query(
                    SemiFinishedVersion.semi_finished_material_id,
                ).filter(
                    SemiFinishedVersion.semi_finished_material_id.in_(
                        semi_ids or {-1},
                    ),
                    SemiFinishedVersion.status == "published",
                ).all()
            }
            missing_semi = [
                item.material_code for item in active_materials
                if item.id in semi_ids and item.id not in published_semi_ids
            ]
            if missing_semi:
                raise ValueError(
                    "以下半成品尚未发布组成：" + "、".join(missing_semi)
                )

            routed_ids = {
                item.id for item in active_materials
                if item.material_type != MaterialType.PURCHASED.value
            }
            published_route_ids = {
                row[0] for row in session.query(
                    MaterialRouteVersion.material_id,
                ).filter(
                    MaterialRouteVersion.material_id.in_(routed_ids or {-1}),
                    MaterialRouteVersion.status == "published",
                ).all()
            }
            missing_routes = [
                item.material_code for item in active_materials
                if item.id in routed_ids and item.id not in published_route_ids
            ]
            if missing_routes:
                raise ValueError(
                    "以下物料尚未发布工艺路线：" + "、".join(missing_routes)
                )

            product.status = "published"
            product.published_by = published_by
            product.published_at = datetime.now()
            session.commit()
            session.refresh(product)
            return cls._serialize_product(session, product)

    @classmethod
    def deactivate_product(cls, product_id: int) -> dict:
        with SessionLocal() as session:
            product = session.query(CatalogProduct).filter(
                CatalogProduct.id == product_id,
            ).with_for_update().one_or_none()
            if product is None:
                raise ValueError("产品不存在")
            if product.status != "published":
                raise ValueError("只有已发布产品可以停用")
            product.status = "inactive"
            session.commit()
            session.refresh(product)
            return cls._serialize_product(session, product)

    @staticmethod
    def delete_unused_material(material_id: int) -> None:
        with SessionLocal() as session:
            material = session.get(Material, material_id)
            if material is None:
                raise ValueError("物料不存在")
            product = session.get(CatalogProduct, material.product_id)
            if product is None or product.status != "draft":
                raise ValueError("只有草稿产品允许删除物料")
            if material.material_type == MaterialType.FINISHED.value:
                raise ValueError("成品物料不能删除")
            referenced = CatalogService._material_is_referenced(
                session,
                material.id,
            )
            if referenced:
                raise ValueError("物料已经被BOM、路线或生产计划引用，只能停用")
            if material.material_type == MaterialType.SEMI_FINISHED.value:
                code_parts = material.material_code.rsplit("-S", 1)
                if len(code_parts) == 2 and code_parts[1].isdigit():
                    session.add(
                        ProductReleasedSemiNumber(
                            product_id=material.product_id,
                            sequence_no=int(code_parts[1]),
                        )
                    )
            session.delete(material)
            session.commit()

    @staticmethod
    def _material_is_referenced(session, material_id: int) -> bool:
        return any(
            session.query(model).filter(column == material_id).first() is not None
            for model, column in (
                (ProductBomItem, ProductBomItem.material_id),
                (
                    SemiFinishedVersion,
                    SemiFinishedVersion.semi_finished_material_id,
                ),
                (SemiFinishedInput, SemiFinishedInput.input_material_id),
                (MaterialRouteVersion, MaterialRouteVersion.material_id),
                (ProductionPlanMaterial, ProductionPlanMaterial.material_id),
                (MaterialInventory, MaterialInventory.material_id),
            )
        )
