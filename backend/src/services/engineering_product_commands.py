from datetime import datetime
from copy import deepcopy

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from database import SessionLocal
from domain.engineering_products import validate_bom_identity, validate_expected_revision
from domain.models import BomItemCommand
from models.engineering import Product
from models.organization import Procedure
from models.sales import CustomerOrderItem
from repositories.engineering_products import EngineeringProductRepository
from schemas.engineering import (
    BomItemPayload,
    CreateProductPayload,
    ProcessFlowPayload,
    UpdateProductPayload,
)
from services.engineering_product_mapper import serialize_product_detail
from services.engineering_product_support import (
    bom_commands,
    empty_process_flow,
    raise_integrity_error,
    raise_stale_data_error,
    validated_flow,
)
from services.errors import DomainError, product_not_found
from services.process_flow_mapping import synchronize_part_metadata


def _result(repository: EngineeringProductRepository, product: Product) -> dict:
    repository.flush()
    return serialize_product_detail(product, empty_process_flow())


def _ensure_version_editable(session, product_id: int, product_version: int) -> None:
    if session.scalar(
        select(CustomerOrderItem.id)
        .where(
            CustomerOrderItem.product_id == product_id,
            CustomerOrderItem.product_version == product_version,
        )
        .limit(1)
    ):
        raise DomainError(
            "product_version_in_use",
            "当前产品版本已被客户订单引用，请创建新版本后修改",
            status_code=409,
        )


def _ensure_product_info_editable(session, product_id: int) -> None:
    if session.scalar(
        select(CustomerOrderItem.id)
        .where(CustomerOrderItem.product_id == product_id)
        .limit(1)
    ):
        raise DomainError(
            "product_info_in_use",
            "产品已被客户订单引用，基础信息不允许修改",
            status_code=409,
        )


def _ensure_procedures_exist(session, flow: ProcessFlowPayload) -> None:
    procedure_ids = {
        node.procedure_id for node in flow.nodes if node.type == "process"
    }
    if not procedure_ids:
        return
    existing_ids = set(
        session.scalars(select(Procedure.id).where(Procedure.id.in_(procedure_ids))).all()
    )
    if existing_ids != procedure_ids:
        raise DomainError(
            "process_procedure_invalid",
            "流程图引用了不存在的工艺",
            path="process_flow.nodes",
        )


def create_product(payload: CreateProductPayload) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = EngineeringProductRepository(session)
            items = bom_commands(payload.bom_items)
            validate_bom_identity(items, existing_ids=set())
            product = Product(
                customer_name=payload.customer_name,
                product_name=payload.product_name,
                factory_code=payload.factory_code,
                customer_code=payload.customer_code,
            )
            repository.add(product)
            repository.flush()
            repository.replace_bom(product, product.version, items)
            repository.set_process_flow(product, product.version, empty_process_flow())
            return _result(repository, product)
    except IntegrityError as exc:
        raise_integrity_error(exc)


def update_product_info(product_id: int, payload: UpdateProductPayload) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = EngineeringProductRepository(session)
            product = repository.get(product_id)
            if product is None:
                raise product_not_found()
            session.refresh(product, with_for_update=True)
            validate_expected_revision(product.revision, payload.expected_revision)
            unchanged = (
                product.customer_name == payload.customer_name
                and product.product_name == payload.product_name
                and product.factory_code == payload.factory_code
                and product.customer_code == payload.customer_code
            )
            if unchanged:
                return _result(repository, product)
            _ensure_product_info_editable(session, product.id)
            product.customer_name = payload.customer_name
            product.product_name = payload.product_name
            product.factory_code = payload.factory_code
            product.customer_code = payload.customer_code
            product.updated_at = datetime.now()
            product.revision += 1
            return _result(repository, product)
    except IntegrityError as exc:
        raise_integrity_error(exc)
    except StaleDataError as exc:
        raise_stale_data_error(exc)


def replace_product_bom(
    product_id: int,
    expected_revision: int,
    items: list[BomItemPayload],
) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = EngineeringProductRepository(session)
            product = repository.get(product_id)
            if product is None:
                raise product_not_found()
            session.refresh(product, with_for_update=True)
            validate_expected_revision(product.revision, expected_revision)
            _ensure_version_editable(session, product.id, product.version)
            commands = bom_commands(items)
            retained_ids = validate_bom_identity(
                commands,
                {
                    item.id
                    for item in product.bom_items
                    if item.product_version == product.version
                },
            )
            current_flow = None
            process_flow_record = next(
                (
                    item
                    for item in product.process_flows
                    if item.product_version == product.version
                ),
                None,
            )
            if process_flow_record is not None:
                current_flow = ProcessFlowPayload.model_validate(
                    process_flow_record.flow_json
                )
                validated_flow(current_flow, retained_ids)
            saved_items = repository.replace_bom(product, product.version, commands)
            if current_flow is not None:
                synchronized = synchronize_part_metadata(
                    current_flow,
                    {item.id: (item.part_name, item.part_no) for item in saved_items},
                )
                repository.set_process_flow(
                    product,
                    product.version,
                    synchronized.model_dump(exclude_none=True),
                )
            product.updated_at = datetime.now()
            product.revision += 1
            return _result(repository, product)
    except IntegrityError as exc:
        raise_integrity_error(exc)
    except StaleDataError as exc:
        raise_stale_data_error(exc)


def update_product_process_flow(
    product_id: int,
    expected_revision: int,
    process_flow: ProcessFlowPayload,
) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = EngineeringProductRepository(session)
            product = repository.get(product_id)
            if product is None:
                raise product_not_found()
            session.refresh(product, with_for_update=True)
            validate_expected_revision(product.revision, expected_revision)
            _ensure_version_editable(session, product.id, product.version)
            flow = synchronize_part_metadata(
                process_flow,
                {
                    item.id: (item.part_name, item.part_no)
                    for item in product.bom_items
                    if item.product_version == product.version
                },
            )
            _ensure_procedures_exist(session, flow)
            repository.set_process_flow(
                product,
                product.version,
                validated_flow(
                    flow,
                    {
                        item.id
                        for item in product.bom_items
                        if item.product_version == product.version
                    },
                ),
            )
            product.updated_at = datetime.now()
            product.revision += 1
            return _result(repository, product)
    except StaleDataError as exc:
        raise_stale_data_error(exc)


def delete_product(product_id: int, expected_revision: int) -> None:
    try:
        with SessionLocal.begin() as session:
            repository = EngineeringProductRepository(session)
            product = repository.get(product_id)
            if product is None:
                raise product_not_found()
            session.refresh(product, with_for_update=True)
            validate_expected_revision(product.revision, expected_revision)
            repository.delete(product)
    except IntegrityError as exc:
        raise DomainError(
            "product_in_use",
            "产品已被客户订单引用，不能删除",
            status_code=409,
        ) from exc
    except StaleDataError as exc:
        raise_stale_data_error(exc)


def create_product_version(product_id: int, expected_revision: int) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = EngineeringProductRepository(session)
            product = repository.get(product_id)
            if product is None:
                raise product_not_found()
            session.refresh(product, with_for_update=True)
            validate_expected_revision(product.revision, expected_revision)
            source_version = product.version
            next_version = source_version + 1
            source_items = [
                item
                for item in product.bom_items
                if item.product_version == source_version
            ]
            copied_items = repository.replace_bom(
                product,
                next_version,
                [
                    BomItemCommand(
                        id=None,
                        part_name=item.part_name,
                        part_no=item.part_no,
                        pcs=item.pcs,
                        remark=item.remark,
                    )
                    for item in source_items
                ],
            )
            repository.flush()
            id_map = {
                source.id: copied.id
                for source, copied in zip(source_items, copied_items, strict=True)
            }
            source_flow = next(
                (
                    item.flow_json
                    for item in product.process_flows
                    if item.product_version == source_version
                ),
                empty_process_flow(),
            )
            copied_flow = deepcopy(source_flow)
            for node in copied_flow.get("nodes", []):
                if node.get("type") == "part":
                    node["bom_item_id"] = id_map[node["bom_item_id"]]
            repository.set_process_flow(product, next_version, copied_flow)
            product.version = next_version
            product.revision += 1
            product.updated_at = datetime.now()
            return _result(repository, product)
    except IntegrityError as exc:
        raise_integrity_error(exc)
