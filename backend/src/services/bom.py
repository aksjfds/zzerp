from datetime import datetime

from sqlalchemy.exc import DBAPIError

from database import SessionLocal
from domain.enums import MaterialType
from models.bom import (
    ProductBomItem,
    ProductBomVersion,
    SemiFinishedInput,
    SemiFinishedVersion,
)
from models.catalog import CatalogProduct, Material
from schemas.bom import ProductBomVersionInput, SemiFinishedVersionInput


def _material_map(session, product_id: int) -> dict[int, Material]:
    materials = session.query(Material).filter(
        Material.product_id == product_id,
    ).all()
    return {item.id: item for item in materials}


class BomService:
    @staticmethod
    def _validate_bom_items(
        session,
        product_id: int,
        payload: ProductBomVersionInput,
    ) -> dict[int, Material]:
        material_ids = [item.material_id for item in payload.items]
        if len(material_ids) != len(set(material_ids)):
            raise ValueError("同一BOM版本不能重复选择配件")
        materials = session.query(Material).filter(
            Material.id.in_(material_ids),
            Material.product_id == product_id,
            Material.active.is_(True),
        ).all()
        if len(materials) != len(material_ids):
            raise ValueError("BOM包含不存在、已停用或属于其他产品的配件")
        allowed_types = {
            MaterialType.SELF_MADE.value,
            MaterialType.PURCHASED.value,
        }
        if any(item.material_type not in allowed_types for item in materials):
            raise ValueError("产品BOM只能包含自制配件和外购配件")
        return {item.id: item for item in materials}

    @staticmethod
    def _serialize_bom_version(
        session,
        version: ProductBomVersion,
        materials: dict[int, Material] | None = None,
    ) -> dict:
        material_lookup = materials or _material_map(session, version.product_id)
        items = session.query(ProductBomItem).filter(
            ProductBomItem.bom_version_id == version.id,
        ).order_by(ProductBomItem.id.asc()).all()
        return {
            "id": version.id,
            "product_id": version.product_id,
            "version_no": version.version_no,
            "status": version.status,
            "items": [
                {
                    "id": item.id,
                    "material_id": item.material_id,
                    "material_code": material_lookup[item.material_id].material_code,
                    "material_name": material_lookup[item.material_id].material_name,
                    "material_type": material_lookup[item.material_id].material_type,
                    "quantity": item.quantity,
                    "unit": item.unit,
                }
                for item in items
            ],
        }

    @classmethod
    def list_bom_versions(cls, product_id: int) -> list[dict]:
        with SessionLocal() as session:
            if session.get(CatalogProduct, product_id) is None:
                raise ValueError("产品不存在")
            materials = _material_map(session, product_id)
            versions = session.query(ProductBomVersion).filter(
                ProductBomVersion.product_id == product_id,
            ).order_by(ProductBomVersion.version_no.desc()).all()
            return [
                cls._serialize_bom_version(session, item, materials)
                for item in versions
            ]

    @classmethod
    def create_bom_version(
        cls,
        product_id: int,
        payload: ProductBomVersionInput,
        created_by: int,
    ) -> dict:
        with SessionLocal() as session:
            product = session.query(CatalogProduct).filter(
                CatalogProduct.id == product_id,
            ).with_for_update().one_or_none()
            if product is None:
                raise ValueError("产品不存在")
            materials = cls._validate_bom_items(session, product_id, payload)
            latest_version = session.query(ProductBomVersion.version_no).filter(
                ProductBomVersion.product_id == product_id,
            ).order_by(ProductBomVersion.version_no.desc()).first()
            version = ProductBomVersion(
                product_id=product_id,
                version_no=(latest_version[0] if latest_version else 0) + 1,
                status="draft",
                created_by=created_by,
            )
            session.add(version)
            session.flush()
            for item in payload.items:
                session.add(
                    ProductBomItem(
                        bom_version_id=version.id,
                        product_id=product_id,
                        material_id=item.material_id,
                        quantity=item.quantity,
                        unit="pcs",
                    )
                )
            session.commit()
            session.refresh(version)
            return cls._serialize_bom_version(session, version, materials)

    @classmethod
    def update_bom_version(
        cls,
        version_id: int,
        payload: ProductBomVersionInput,
    ) -> dict:
        with SessionLocal() as session:
            version = session.get(ProductBomVersion, version_id)
            if version is None:
                raise ValueError("BOM版本不存在")
            if version.status != "draft":
                raise ValueError("只有草稿BOM版本允许修改")
            materials = cls._validate_bom_items(
                session,
                version.product_id,
                payload,
            )
            session.query(ProductBomItem).filter(
                ProductBomItem.bom_version_id == version.id,
            ).delete()
            for item in payload.items:
                session.add(
                    ProductBomItem(
                        bom_version_id=version.id,
                        product_id=version.product_id,
                        material_id=item.material_id,
                        quantity=item.quantity,
                        unit="pcs",
                    )
                )
            session.commit()
            return cls._serialize_bom_version(session, version, materials)

    @classmethod
    def publish_bom_version(cls, version_id: int, published_by: int) -> dict:
        with SessionLocal() as session:
            version = session.get(ProductBomVersion, version_id)
            if version is None:
                raise ValueError("BOM版本不存在")
            if version.status != "draft":
                raise ValueError("只有草稿BOM版本允许发布")
            items = session.query(ProductBomItem).filter(
                ProductBomItem.bom_version_id == version.id,
            ).all()
            if not items:
                raise ValueError("BOM没有配件，不能发布")
            cls._validate_bom_items(
                session,
                version.product_id,
                ProductBomVersionInput(
                    items=[
                        {"material_id": item.material_id, "quantity": item.quantity}
                        for item in items
                    ]
                ),
            )
            current = session.query(ProductBomVersion).filter(
                ProductBomVersion.product_id == version.product_id,
                ProductBomVersion.status == "published",
            ).one_or_none()
            if current is not None:
                current.status = "inactive"
                session.flush()
            version.status = "published"
            version.published_by = published_by
            version.published_at = datetime.now()
            session.commit()
            session.refresh(version)
            return cls._serialize_bom_version(session, version)

    @staticmethod
    def delete_bom_version(version_id: int) -> None:
        with SessionLocal() as session:
            version = session.get(ProductBomVersion, version_id)
            if version is None:
                raise ValueError("BOM版本不存在")
            if version.status != "draft":
                raise ValueError("只有草稿BOM版本允许删除")
            session.query(ProductBomItem).filter(
                ProductBomItem.bom_version_id == version.id,
            ).delete()
            session.delete(version)
            session.commit()

    @staticmethod
    def _validate_semi_inputs(
        session,
        semi_material: Material,
        payload: SemiFinishedVersionInput,
    ) -> dict[int, Material]:
        input_ids = [item.input_material_id for item in payload.inputs]
        if len(input_ids) != len(set(input_ids)):
            raise ValueError("同一半成品不能重复选择输入物料")
        if semi_material.id in input_ids:
            raise ValueError("半成品不能包含自身")
        materials = session.query(Material).filter(
            Material.id.in_(input_ids),
            Material.product_id == semi_material.product_id,
            Material.active.is_(True),
        ).all()
        if len(materials) != len(input_ids):
            raise ValueError("输入物料不存在、已停用或属于其他产品")
        if any(item.material_type == MaterialType.FINISHED.value for item in materials):
            raise ValueError("成品不能作为半成品输入")
        return {item.id: item for item in materials}

    @staticmethod
    def _serialize_semi_version(
        session,
        version: SemiFinishedVersion,
        materials: dict[int, Material] | None = None,
    ) -> dict:
        material_lookup = materials or _material_map(session, version.product_id)
        output = material_lookup[version.semi_finished_material_id]
        inputs = session.query(SemiFinishedInput).filter(
            SemiFinishedInput.semi_finished_version_id == version.id,
        ).order_by(SemiFinishedInput.id.asc()).all()
        return {
            "id": version.id,
            "semi_finished_material_id": version.semi_finished_material_id,
            "material_code": output.material_code,
            "material_name": output.material_name,
            "version_no": version.version_no,
            "quantity_per_finished": version.quantity_per_finished,
            "status": version.status,
            "inputs": [
                {
                    "id": item.id,
                    "input_material_id": item.input_material_id,
                    "material_code": material_lookup[item.input_material_id].material_code,
                    "material_name": material_lookup[item.input_material_id].material_name,
                    "material_type": material_lookup[item.input_material_id].material_type,
                    "quantity": item.quantity,
                    "unit": item.unit,
                }
                for item in inputs
            ],
        }

    @classmethod
    def list_semi_versions(cls, product_id: int) -> list[dict]:
        with SessionLocal() as session:
            materials = _material_map(session, product_id)
            if not materials and session.get(CatalogProduct, product_id) is None:
                raise ValueError("产品不存在")
            versions = session.query(SemiFinishedVersion).filter(
                SemiFinishedVersion.product_id == product_id,
            ).order_by(
                SemiFinishedVersion.semi_finished_material_id.asc(),
                SemiFinishedVersion.version_no.desc(),
            ).all()
            return [
                cls._serialize_semi_version(session, item, materials)
                for item in versions
            ]

    @classmethod
    def create_semi_version(
        cls,
        semi_material_id: int,
        payload: SemiFinishedVersionInput,
        created_by: int,
    ) -> dict:
        with SessionLocal() as session:
            semi_material = session.query(Material).filter(
                Material.id == semi_material_id,
            ).with_for_update().one_or_none()
            if (
                semi_material is None
                or semi_material.material_type != MaterialType.SEMI_FINISHED.value
            ):
                raise ValueError("半成品物料不存在")
            materials = cls._validate_semi_inputs(session, semi_material, payload)
            materials[semi_material.id] = semi_material
            latest_version = session.query(SemiFinishedVersion.version_no).filter(
                SemiFinishedVersion.semi_finished_material_id == semi_material.id,
            ).order_by(SemiFinishedVersion.version_no.desc()).first()
            version = SemiFinishedVersion(
                semi_finished_material_id=semi_material.id,
                product_id=semi_material.product_id,
                version_no=(latest_version[0] if latest_version else 0) + 1,
                quantity_per_finished=payload.quantity_per_finished,
                status="draft",
                created_by=created_by,
            )
            session.add(version)
            session.flush()
            for item in payload.inputs:
                session.add(
                    SemiFinishedInput(
                        semi_finished_version_id=version.id,
                        product_id=semi_material.product_id,
                        input_material_id=item.input_material_id,
                        quantity=item.quantity,
                        unit="pcs",
                    )
                )
            try:
                session.commit()
            except DBAPIError as exc:
                session.rollback()
                raise ValueError("半成品组成无效或形成循环引用") from exc
            session.refresh(version)
            return cls._serialize_semi_version(session, version, materials)

    @classmethod
    def update_semi_version(
        cls,
        version_id: int,
        payload: SemiFinishedVersionInput,
    ) -> dict:
        with SessionLocal() as session:
            version = session.get(SemiFinishedVersion, version_id)
            if version is None:
                raise ValueError("半成品版本不存在")
            if version.status != "draft":
                raise ValueError("只有草稿半成品版本允许修改")
            semi_material = session.get(Material, version.semi_finished_material_id)
            materials = cls._validate_semi_inputs(session, semi_material, payload)
            materials[semi_material.id] = semi_material
            session.query(SemiFinishedInput).filter(
                SemiFinishedInput.semi_finished_version_id == version.id,
            ).delete()
            version.quantity_per_finished = payload.quantity_per_finished
            for item in payload.inputs:
                session.add(
                    SemiFinishedInput(
                        semi_finished_version_id=version.id,
                        product_id=version.product_id,
                        input_material_id=item.input_material_id,
                        quantity=item.quantity,
                        unit="pcs",
                    )
                )
            try:
                session.commit()
            except DBAPIError as exc:
                session.rollback()
                raise ValueError("半成品组成无效或形成循环引用") from exc
            return cls._serialize_semi_version(session, version, materials)

    @classmethod
    def publish_semi_version(cls, version_id: int, published_by: int) -> dict:
        with SessionLocal() as session:
            version = session.get(SemiFinishedVersion, version_id)
            if version is None:
                raise ValueError("半成品版本不存在")
            if version.status != "draft":
                raise ValueError("只有草稿半成品版本允许发布")
            inputs = session.query(SemiFinishedInput).filter(
                SemiFinishedInput.semi_finished_version_id == version.id,
            ).all()
            if not inputs:
                raise ValueError("半成品没有输入物料，不能发布")
            semi_material = session.get(Material, version.semi_finished_material_id)
            cls._validate_semi_inputs(
                session,
                semi_material,
                SemiFinishedVersionInput(
                    quantity_per_finished=version.quantity_per_finished,
                    inputs=[
                        {
                            "input_material_id": item.input_material_id,
                            "quantity": item.quantity,
                        }
                        for item in inputs
                    ],
                ),
            )
            current = session.query(SemiFinishedVersion).filter(
                SemiFinishedVersion.semi_finished_material_id
                == version.semi_finished_material_id,
                SemiFinishedVersion.status == "published",
            ).one_or_none()
            if current is not None:
                current.status = "inactive"
                session.flush()
            version.status = "published"
            version.published_by = published_by
            version.published_at = datetime.now()
            session.commit()
            session.refresh(version)
            return cls._serialize_semi_version(session, version)

    @staticmethod
    def delete_semi_version(version_id: int) -> None:
        with SessionLocal() as session:
            version = session.get(SemiFinishedVersion, version_id)
            if version is None:
                raise ValueError("半成品版本不存在")
            if version.status != "draft":
                raise ValueError("只有草稿半成品版本允许删除")
            session.query(SemiFinishedInput).filter(
                SemiFinishedInput.semi_finished_version_id == version.id,
            ).delete()
            session.delete(version)
            session.commit()

    @classmethod
    def production_structure(cls, product_id: int) -> dict:
        with SessionLocal() as session:
            product = session.get(CatalogProduct, product_id)
            if product is None:
                raise ValueError("产品不存在")
            materials = _material_map(session, product_id)
            finished = next(
                (
                    item
                    for item in materials.values()
                    if item.material_type == MaterialType.FINISHED.value
                ),
                None,
            )
            bom = session.query(ProductBomVersion).filter(
                ProductBomVersion.product_id == product_id,
                ProductBomVersion.status == "published",
            ).one_or_none()
            if finished is None or bom is None:
                raise ValueError("产品尚未发布BOM")
            bom_items = session.query(ProductBomItem).filter(
                ProductBomItem.bom_version_id == bom.id,
            ).all()
            semi_versions = session.query(SemiFinishedVersion).filter(
                SemiFinishedVersion.product_id == product_id,
                SemiFinishedVersion.status == "published",
            ).all()
            semi_inputs: dict[int, list[SemiFinishedInput]] = {}
            used_material_ids: set[int] = set()
            for version in semi_versions:
                inputs = session.query(SemiFinishedInput).filter(
                    SemiFinishedInput.semi_finished_version_id == version.id,
                ).all()
                semi_inputs[version.semi_finished_material_id] = inputs
                used_material_ids.update(item.input_material_id for item in inputs)

            top_semis = [
                item
                for item in semi_versions
                if item.semi_finished_material_id not in used_material_ids
            ]
            direct_parts = [
                item
                for item in bom_items
                if item.material_id not in used_material_ids
            ]

            def material_node(
                material_id: int,
                quantity: int,
                path: tuple[int, ...],
            ) -> dict:
                if material_id in path:
                    raise ValueError("半成品组成存在循环引用")
                material = materials[material_id]
                children = [
                    material_node(
                        item.input_material_id,
                        item.quantity,
                        (*path, material_id),
                    )
                    for item in semi_inputs.get(material_id, [])
                ]
                return {
                    "id": "material-" + "-".join(
                        str(item) for item in (*path, material_id)
                    ),
                    "material_id": material.id,
                    "material_code": material.material_code,
                    "material_name": material.material_name,
                    "material_type": material.material_type,
                    "quantity": quantity,
                    "children": children,
                }

            children = [
                material_node(
                    item.semi_finished_material_id,
                    item.quantity_per_finished,
                    (),
                )
                for item in top_semis
            ]
            children.extend(
                material_node(item.material_id, item.quantity, ())
                for item in direct_parts
            )
            return {
                "product_id": product_id,
                "bom_version_id": bom.id,
                "root": {
                    "id": f"material-{finished.id}",
                    "material_id": finished.id,
                    "material_code": finished.material_code,
                    "material_name": finished.material_name,
                    "material_type": finished.material_type,
                    "quantity": 1,
                    "children": children,
                },
            }
