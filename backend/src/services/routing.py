from datetime import datetime

from database import SessionLocal
from domain.enums import MaterialType, RouteStepType
from models.catalog import CatalogProduct, Material
from models.organization import Department, Workshop
from models.routing import MaterialRouteStep, MaterialRouteVersion
from schemas.routing import MaterialRouteInput


class RoutingService:
    @staticmethod
    def _validate_steps(session, payload: MaterialRouteInput) -> dict:
        external_positions = [
            index
            for index, item in enumerate(payload.steps)
            if item.step_type == RouteStepType.EXTERNAL_SURFACE
        ]
        if len(external_positions) > 1:
            raise ValueError("一条物料路线最多只能有一个外厂表面处理步骤")
        if external_positions and external_positions[0] != len(payload.steps) - 1:
            raise ValueError("外厂表面处理必须是该物料路线的最后一步")
        internal_steps = [
            item
            for item in payload.steps
            if item.step_type == RouteStepType.INTERNAL
        ]
        if not internal_steps:
            raise ValueError("物料路线至少需要一个内部生产部门和车间")
        department_ids = {item.department_id for item in internal_steps}
        workshop_ids = {item.workshop_id for item in internal_steps}
        if any(item is None for item in department_ids | workshop_ids):
            raise ValueError("内部生产步骤必须选择部门和车间")
        if any(
            item.department_id is not None or item.workshop_id is not None
            for item in payload.steps
            if item.step_type == RouteStepType.EXTERNAL_SURFACE
        ):
            raise ValueError("外厂表面处理步骤不能选择内部部门或车间")

        departments = session.query(Department).filter(
            Department.id.in_(department_ids),
            Department.active.is_(True),
        ).all()
        workshops = session.query(Workshop).filter(
            Workshop.id.in_(workshop_ids),
            Workshop.active.is_(True),
        ).all()
        department_map = {item.id: item for item in departments}
        workshop_map = {item.id: item for item in workshops}
        if len(department_map) != len(department_ids):
            raise ValueError("路线包含不存在或已停用的部门")
        if len(workshop_map) != len(workshop_ids):
            raise ValueError("路线包含不存在或已停用的车间")
        for item in internal_steps:
            department = department_map[item.department_id]
            workshop = workshop_map[item.workshop_id]
            if department.department_type != "production":
                raise ValueError("内部生产路线只能选择生产部门")
            if workshop.department_id != department.id:
                raise ValueError("所选车间不属于对应部门")
        return {
            "departments": department_map,
            "workshops": workshop_map,
        }

    @staticmethod
    def _serialize(session, version: MaterialRouteVersion) -> dict:
        material = session.get(Material, version.material_id)
        steps = session.query(MaterialRouteStep).filter(
            MaterialRouteStep.route_version_id == version.id,
        ).order_by(MaterialRouteStep.sequence_no.asc()).all()
        department_ids = {item.department_id for item in steps if item.department_id}
        workshop_ids = {item.workshop_id for item in steps if item.workshop_id}
        departments = {
            item.id: item
            for item in session.query(Department).filter(
                Department.id.in_(department_ids)
            ).all()
        }
        workshops = {
            item.id: item
            for item in session.query(Workshop).filter(
                Workshop.id.in_(workshop_ids)
            ).all()
        }
        return {
            "id": version.id,
            "material_id": material.id,
            "material_code": material.material_code,
            "material_name": material.material_name,
            "version_no": version.version_no,
            "status": version.status,
            "steps": [
                {
                    "id": item.id,
                    "sequence_no": item.sequence_no,
                    "step_type": item.step_type,
                    "department_id": item.department_id,
                    "workshop_id": item.workshop_id,
                    "department_name": (
                        departments[item.department_id].department_name
                        if item.department_id else None
                    ),
                    "workshop_name": (
                        workshops[item.workshop_id].workshop_name
                        if item.workshop_id else None
                    ),
                }
                for item in steps
            ],
        }

    @classmethod
    def list_routes(cls, product_id: int) -> list[dict]:
        with SessionLocal() as session:
            if session.get(CatalogProduct, product_id) is None:
                raise ValueError("产品不存在")
            versions = session.query(MaterialRouteVersion).filter(
                MaterialRouteVersion.product_id == product_id,
            ).order_by(
                MaterialRouteVersion.material_id.asc(),
                MaterialRouteVersion.version_no.desc(),
            ).all()
            return [cls._serialize(session, item) for item in versions]

    @classmethod
    def create_route(
        cls,
        material_id: int,
        payload: MaterialRouteInput,
        created_by: int,
    ) -> dict:
        with SessionLocal() as session:
            material = session.query(Material).filter(
                Material.id == material_id,
            ).with_for_update().one_or_none()
            if material is None or not material.active:
                raise ValueError("物料不存在或已停用")
            if material.material_type == MaterialType.PURCHASED.value:
                raise ValueError("外购配件不能配置生产路线")
            cls._validate_steps(session, payload)
            latest = session.query(MaterialRouteVersion.version_no).filter(
                MaterialRouteVersion.material_id == material.id,
            ).order_by(MaterialRouteVersion.version_no.desc()).first()
            version = MaterialRouteVersion(
                material_id=material.id,
                product_id=material.product_id,
                version_no=(latest[0] if latest else 0) + 1,
                status="draft",
                created_by=created_by,
            )
            session.add(version)
            session.flush()
            cls._replace_steps(session, version, payload)
            session.commit()
            session.refresh(version)
            return cls._serialize(session, version)

    @staticmethod
    def _replace_steps(
        session,
        version: MaterialRouteVersion,
        payload: MaterialRouteInput,
    ) -> None:
        session.query(MaterialRouteStep).filter(
            MaterialRouteStep.route_version_id == version.id,
        ).delete()
        for sequence_no, item in enumerate(payload.steps, start=1):
            session.add(
                MaterialRouteStep(
                    route_version_id=version.id,
                    sequence_no=sequence_no,
                    step_type=item.step_type.value,
                    department_id=item.department_id,
                    workshop_id=item.workshop_id,
                )
            )

    @classmethod
    def update_route(cls, version_id: int, payload: MaterialRouteInput) -> dict:
        with SessionLocal() as session:
            version = session.get(MaterialRouteVersion, version_id)
            if version is None:
                raise ValueError("路线版本不存在")
            if version.status != "draft":
                raise ValueError("只有草稿路线版本允许修改")
            cls._validate_steps(session, payload)
            cls._replace_steps(session, version, payload)
            session.commit()
            return cls._serialize(session, version)

    @classmethod
    def publish_route(cls, version_id: int, published_by: int) -> dict:
        with SessionLocal() as session:
            version = session.get(MaterialRouteVersion, version_id)
            if version is None:
                raise ValueError("路线版本不存在")
            if version.status != "draft":
                raise ValueError("只有草稿路线版本允许发布")
            material = session.get(Material, version.material_id)
            if material is None or not material.active:
                raise ValueError("物料不存在或已停用")
            steps = session.query(MaterialRouteStep).filter(
                MaterialRouteStep.route_version_id == version.id,
            ).order_by(MaterialRouteStep.sequence_no.asc()).all()
            if not steps:
                raise ValueError("空路线不能发布")
            cls._validate_steps(
                session,
                MaterialRouteInput(
                    steps=[
                        {
                            "step_type": item.step_type,
                            "department_id": item.department_id,
                            "workshop_id": item.workshop_id,
                        }
                        for item in steps
                    ]
                ),
            )
            current = session.query(MaterialRouteVersion).filter(
                MaterialRouteVersion.material_id == version.material_id,
                MaterialRouteVersion.status == "published",
            ).one_or_none()
            if current is not None:
                current.status = "inactive"
                session.flush()
            version.status = "published"
            version.published_by = published_by
            version.published_at = datetime.now()
            session.commit()
            session.refresh(version)
            return cls._serialize(session, version)

    @staticmethod
    def delete_route(version_id: int) -> None:
        with SessionLocal() as session:
            version = session.get(MaterialRouteVersion, version_id)
            if version is None:
                raise ValueError("路线版本不存在")
            if version.status != "draft":
                raise ValueError("只有草稿路线版本允许删除")
            session.query(MaterialRouteStep).filter(
                MaterialRouteStep.route_version_id == version.id,
            ).delete()
            session.delete(version)
            session.commit()
