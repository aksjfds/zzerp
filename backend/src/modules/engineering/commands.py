from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from database import SessionLocal
from domain.engineering_products import validate_bom_identity, validate_expected_revision
from domain.time import utc_now
from modules.engineering.command_support import command_result, ensure_version_exists
from modules.engineering.collaboration_contract import EngineeringCollaborators
from modules.engineering.editability import (
    ensure_base_info_editable,
    ensure_product_version_editable,
)
from modules.engineering.flow_identity import (
    ensure_priced_bom_items_retained,
    ensure_priced_flow_node_identities_preserved,
)
from modules.engineering.flow_mapping import synchronize_part_metadata
from modules.engineering.persistence import Product, ProductVersion
from modules.engineering.repository import EngineeringProductRepository
from modules.engineering.support import (
    bom_commands,
    empty_process_flow,
    raise_integrity_error,
    raise_stale_data_error,
    validated_draft_flow,
    validated_flow,
)
from schemas.engineering import (
    BomItemPayload,
    CreateProductPayload,
    ProcessFlowPayload,
    UpdateProductPayload,
)
from modules.errors import DomainError, product_not_found
from modules.organization.read_api import (
    get_department_ids_by_codes,
    get_workshop_routes,
)
from modules.sales.customer_api import resolve_customer


def _ensure_workshops_exist(session, flow: ProcessFlowPayload) -> None:
    workshop_ids = {
        node.workshop_id
        for node in flow.nodes
        if node.type in {"process", "assembly"}
    }
    if not workshop_ids:
        return
    workshops = get_workshop_routes(session, workshop_ids)
    existing_ids = set(workshops)
    if existing_ids != workshop_ids:
        invalid_node = next(
            node
            for node in flow.nodes
            if node.type in {"process", "assembly"}
            and node.workshop_id not in existing_ids
        )
        raise DomainError(
            "process_workshop_invalid",
            f"流程节点“{invalid_node.label}”引用的车间不存在，请重新选择车间",
            path="process_flow.nodes",
            element_id=invalid_node.id,
        )
    for node in flow.nodes:
        if node.type in {"process", "assembly"}:
            node.label = workshops[node.workshop_id].workshop_name


def _validate_flow_departments_and_workshops(
    session,
    flow: ProcessFlowPayload,
) -> None:
    workshop_ids = {
        node.workshop_id for node in flow.nodes if node.type in {"process", "assembly"}
    }
    workshops = get_workshop_routes(session, workshop_ids)
    department_ids = get_department_ids_by_codes(
        session,
        {"assembly", "finished", "qc"},
    )
    required_department_codes = {
        code
        for code, node_type in (
            ("assembly", "assembly"),
            ("finished", "shipping"),
            ("qc", "qc"),
        )
        if any(node.type == node_type for node in flow.nodes)
    }
    missing_department_codes = required_department_codes - set(department_ids)
    if missing_department_codes:
        missing_code = sorted(missing_department_codes)[0]
        missing_type = {
            "assembly": "assembly",
            "finished": "shipping",
            "qc": "qc",
        }[missing_code]
        invalid_node = next(
            (node for node in flow.nodes if node.type == missing_type),
            None,
        )
        raise DomainError(
            "flow_department_missing",
            f"流程所需部门不存在：{', '.join(sorted(missing_department_codes))}",
            path="process_flow.nodes",
            element_id=invalid_node.id if invalid_node else None,
        )

    for node in flow.nodes:
        if node.type in {"process", "assembly"}:
            workshop = workshops.get(node.workshop_id)
            if workshop is None:
                raise DomainError(
                    "process_workshop_invalid",
                    f"流程节点“{node.label}”引用的车间不存在，请重新选择车间",
                    path="process_flow.nodes",
                    element_id=node.id,
                )
        if node.type == "assembly":
            workshop = workshops.get(node.workshop_id)
            if workshop is None or workshop.department_id != department_ids.get("assembly"):
                raise DomainError(
                    "assembly_workshop_department_invalid",
                    f"装配节点“{node.label}”关联的车间不属于装配部",
                    path="process_flow.nodes",
                    element_id=node.id,
                )


def create_product(payload: CreateProductPayload) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = EngineeringProductRepository(session)
            items = bom_commands(payload.bom_items)
            validate_bom_identity(items, existing_ids=set())
            customer = resolve_customer(
                session,
                payload.customer_id,
                payload.customer_name,
                allow_create=True,
            )
            product = Product(
                customer_id=customer.id,
                product_name=payload.product_name,
                factory_code=payload.factory_code,
                customer_code=payload.customer_code,
            )
            product.versions.append(ProductVersion(version=1))
            repository.add(product)
            repository.flush()
            repository.replace_bom(product, product.version, items)
            repository.set_process_flow(product, product.version, empty_process_flow())
            return command_result(repository, product)
    except IntegrityError as exc:
        raise_integrity_error(exc)


def update_product_info(
    product_id: int,
    payload: UpdateProductPayload,
    collaborators: EngineeringCollaborators,
) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = EngineeringProductRepository(session)
            product = repository.get(product_id)
            if product is None:
                raise product_not_found()
            session.refresh(product, with_for_update=True)
            validate_expected_revision(product.revision, payload.expected_revision)
            customer = resolve_customer(
                session,
                payload.customer_id,
                payload.customer_name,
                allow_create=True,
            )
            unchanged = (
                product.customer_id == customer.id
                and product.product_name == payload.product_name
                and product.factory_code == payload.factory_code
                and product.customer_code == payload.customer_code
            )
            if unchanged:
                return command_result(repository, product)
            ensure_base_info_editable(session, product.id, collaborators)
            if product.factory_code != payload.factory_code:
                for flow_record in product.process_flows:
                    version_bom = {
                        item.id: (item.part_name, item.part_no)
                        for item in product.bom_items
                        if item.product_version == flow_record.product_version
                    }
                    synchronized = synchronize_part_metadata(
                        ProcessFlowPayload.model_validate(flow_record.flow_json),
                        version_bom,
                        payload.factory_code,
                    )
                    repository.set_process_flow(
                        product,
                        flow_record.product_version,
                        synchronized.model_dump(exclude_none=True),
                    )
            product.customer_id = customer.id
            product.product_name = payload.product_name
            product.factory_code = payload.factory_code
            product.customer_code = payload.customer_code
            product.updated_at = utc_now()
            product.revision += 1
            return command_result(repository, product)
    except IntegrityError as exc:
        raise_integrity_error(exc)
    except StaleDataError as exc:
        raise_stale_data_error(exc)


def replace_product_bom(
    product_id: int,
    expected_revision: int,
    product_version: int,
    items: list[BomItemPayload],
    collaborators: EngineeringCollaborators,
) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = EngineeringProductRepository(session)
            product = repository.get(product_id)
            if product is None:
                raise product_not_found()
            session.refresh(product, with_for_update=True)
            validate_expected_revision(product.revision, expected_revision)
            ensure_version_exists(product, product_version)
            ensure_product_version_editable(session, product.id, product_version, collaborators)
            commands = bom_commands(items)
            retained_ids = validate_bom_identity(
                commands,
                {
                    item.id
                    for item in product.bom_items
                    if item.product_version == product_version
                },
            )
            ensure_priced_bom_items_retained(
                session,
                product_id=product.id,
                product_version=product_version,
                retained_bom_ids=retained_ids,
                collaborators=collaborators,
            )
            current_flow = None
            process_flow_record = next(
                (
                    item
                    for item in product.process_flows
                    if item.product_version == product_version
                ),
                None,
            )
            if process_flow_record is not None:
                current_flow = ProcessFlowPayload.model_validate(
                    process_flow_record.flow_json
                )
                validated_flow(current_flow, retained_ids)
            saved_items = repository.replace_bom(product, product_version, commands)
            if current_flow is not None:
                synchronized = synchronize_part_metadata(
                    current_flow,
                    {item.id: (item.part_name, item.part_no) for item in saved_items},
                    product.factory_code,
                )
                repository.set_process_flow(
                    product,
                    product_version,
                    synchronized.model_dump(exclude_none=True),
                )
            product.updated_at = utc_now()
            product.revision += 1
            return command_result(repository, product, product_version)
    except IntegrityError as exc:
        raise_integrity_error(exc)
    except StaleDataError as exc:
        raise_stale_data_error(exc)


def update_product_process_flow(
    product_id: int,
    expected_revision: int,
    product_version: int,
    process_flow: ProcessFlowPayload,
    collaborators: EngineeringCollaborators,
) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = EngineeringProductRepository(session)
            product = repository.get(product_id)
            if product is None:
                raise product_not_found()
            session.refresh(product, with_for_update=True)
            validate_expected_revision(product.revision, expected_revision)
            ensure_version_exists(product, product_version)
            ensure_product_version_editable(session, product.id, product_version, collaborators)
            flow = synchronize_part_metadata(
                process_flow,
                {
                    item.id: (item.part_name, item.part_no)
                    for item in product.bom_items
                    if item.product_version == product_version
                },
                product.factory_code,
            )
            validated = validated_flow(
                flow,
                {
                    item.id
                    for item in product.bom_items
                    if item.product_version == product_version
                },
            )
            current_flow_record = next(
                (
                    item
                    for item in product.process_flows
                    if item.product_version == product_version
                ),
                None,
            )
            ensure_priced_flow_node_identities_preserved(
                session,
                product_id=product.id,
                product_version=product_version,
                current_flow=(current_flow_record.flow_json if current_flow_record else {}),
                proposed_flow=validated,
                collaborators=collaborators,
            )
            _ensure_workshops_exist(session, flow)
            _validate_flow_departments_and_workshops(session, flow)
            repository.set_process_flow(
                product,
                product_version,
                validated,
            )
            repository.flush()
            product.updated_at = utc_now()
            product.revision += 1
            return command_result(repository, product, product_version)
    except IntegrityError as exc:
        raise_integrity_error(exc)
    except StaleDataError as exc:
        raise_stale_data_error(exc)


def save_product_process_flow_draft(
    product_id: int,
    expected_revision: int,
    product_version: int,
    process_flow: ProcessFlowPayload,
    collaborators: EngineeringCollaborators,
) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = EngineeringProductRepository(session)
            product = repository.get(product_id)
            if product is None:
                raise product_not_found()
            session.refresh(product, with_for_update=True)
            validate_expected_revision(product.revision, expected_revision)
            ensure_version_exists(product, product_version)
            ensure_product_version_editable(session, product.id, product_version, collaborators)
            bom_items = {
                item.id: (item.part_name, item.part_no)
                for item in product.bom_items
                if item.product_version == product_version
            }
            validated_draft_flow(process_flow, set(bom_items))
            flow = synchronize_part_metadata(
                process_flow,
                bom_items,
                product.factory_code,
            )
            validated = flow.model_dump(exclude_none=True)
            _ensure_workshops_exist(session, flow)
            _validate_flow_departments_and_workshops(session, flow)
            repository.set_process_flow_draft(product, product_version, validated)
            repository.flush()
            product.updated_at = utc_now()
            product.revision += 1
            return command_result(repository, product, product_version)
    except IntegrityError as exc:
        raise_integrity_error(exc)
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
