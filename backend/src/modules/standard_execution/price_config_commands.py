"""Procedure configuration and piece-price mutation commands."""

from sqlalchemy import select

from database import SessionLocal
from domain.time import utc_now
from modules.errors import DomainError
from modules.organization.read_api import get_department_procedure_routes
from modules.organization.transaction_api import delete_procedure, resolve_workshop_procedure
from modules.production_core.reference_api import (
    has_standard_execution_order,
    has_work_order_for_procedure,
    list_standard_execution_order_ids,
    temporary_work_order_price_reference,
)
from modules.standard_execution.persistence import ProcedureConfiguration, ProcedurePrice, WorkOrderPayDetail
from modules.standard_execution.price_config_support import (
    _department,
    _record_price_revision,
    _resolve_configuration_scope,
)
from schemas.procedure_prices import ProcedurePriceUpdate, TemporaryWorkOrderPriceUpdate


def update_temporary_work_order_price(
    department_code: str,
    work_order_id: int,
    payload: TemporaryWorkOrderPriceUpdate,
    user_department: str | None,
    user_is_system: bool,
    actor_username: str,
) -> None:
    with SessionLocal.begin() as session:
        department = _department(
            session,
            department_code,
            user_department,
            user_is_system,
        )
        reference = temporary_work_order_price_reference(session, work_order_id)
        if reference is None:
            raise DomainError(
                "temporary_work_order_not_found",
                "临时工单不存在",
                status_code=404,
            )
        department_procedure_ids = {
            item.id
            for item in get_department_procedure_routes(session, department.id)
        }
        if reference.procedure_id not in department_procedure_ids:
            raise DomainError(
                "temporary_work_order_department_invalid",
                "临时工单不属于当前部门",
                status_code=403,
            )
        pay_detail = session.scalar(
            select(WorkOrderPayDetail).where(
                WorkOrderPayDetail.work_order_id == work_order_id,
                WorkOrderPayDetail.procedure_id == reference.procedure_id,
            ).with_for_update()
        )
        if pay_detail is None:
            raise DomainError(
                "temporary_work_order_price_context_invalid",
                "临时工单计价信息不完整",
                status_code=409,
            )
        _record_price_revision(
            session,
            department_id=department.id,
            target_type="temporary",
            target_id=pay_detail.id,
            target_label=f"临时工单 {reference.work_order_no} · {pay_detail.procedure_name}",
            previous_unit_price=pay_detail.unit_price,
            new_unit_price=payload.unit_price,
            actor_username=actor_username,
        )
        pay_detail.unit_price = payload.unit_price


def update_procedure_price(
    department_code: str,
    product_id: int,
    product_version: int,
    origin_flow_node_id: str,
    flow_node_id: str,
    payload: ProcedurePriceUpdate,
    user_department: str | None,
    user_is_system: bool,
    actor_username: str,
) -> None:
    with SessionLocal.begin() as session:
        _save_procedure_configuration(
            session,
            department_code,
            product_id,
            product_version,
            origin_flow_node_id,
            flow_node_id,
            payload,
            user_department,
            user_is_system,
            actor_username,
            confirm=False,
        )


def confirm_procedure_configuration(
    department_code: str,
    product_id: int,
    product_version: int,
    origin_flow_node_id: str,
    flow_node_id: str,
    payload: ProcedurePriceUpdate,
    user_department: str | None,
    user_is_system: bool,
    actor_username: str,
) -> None:
    with SessionLocal.begin() as session:
        _save_procedure_configuration(
            session,
            department_code,
            product_id,
            product_version,
            origin_flow_node_id,
            flow_node_id,
            payload,
            user_department,
            user_is_system,
            actor_username,
            confirm=True,
        )


def cancel_procedure_configuration(
    department_code: str,
    product_id: int,
    product_version: int,
    origin_flow_node_id: str,
    flow_node_id: str,
    user_department: str | None,
    user_is_system: bool,
) -> None:
    with SessionLocal.begin() as session:
        scope = _resolve_configuration_scope(
            session,
            department_code,
            product_id,
            product_version,
            origin_flow_node_id,
            flow_node_id,
            user_department,
            user_is_system,
        )
        configuration = session.scalar(
            select(ProcedureConfiguration).where(
                ProcedureConfiguration.product_id == product_id,
                ProcedureConfiguration.product_version == product_version,
                ProcedureConfiguration.material_key == scope.material_key,
                ProcedureConfiguration.flow_node_id == flow_node_id,
            ).with_for_update()
        )
        if configuration is None or configuration.confirmed_at is None:
            raise DomainError(
                "procedure_configuration_not_confirmed",
                "工艺配置尚未确认",
                status_code=409,
            )
        if list_standard_execution_order_ids(
            session,
            product_id=product_id,
            product_version=product_version,
            origin_flow_node_id=origin_flow_node_id,
            flow_node_id=flow_node_id,
        ):
            raise DomainError(
                "procedure_configuration_in_use",
                "当前配置已经开过工单，不能取消确认",
                status_code=409,
            )
        configuration.confirmed_at = None
        configuration.confirmed_by = None


def _save_procedure_configuration(
    session,
    department_code: str,
    product_id: int,
    product_version: int,
    origin_flow_node_id: str,
    flow_node_id: str,
    payload: ProcedurePriceUpdate,
    user_department: str | None,
    user_is_system: bool,
    actor_username: str,
    *,
    confirm: bool,
) -> None:
    scope = _resolve_configuration_scope(
        session,
        department_code,
        product_id,
        product_version,
        origin_flow_node_id,
        flow_node_id,
        user_department,
        user_is_system,
    )
    normalized: dict[str, tuple[int | None, object]] = {}
    for item in payload.procedures:
        name = item.procedure_name.strip()
        if name in normalized:
            raise DomainError("procedure_name_duplicate", "同一车间不能重复配置同名工艺")
        normalized[name] = (item.procedure_id, item.unit_price)
    configuration = session.scalar(
        select(ProcedureConfiguration).where(
            ProcedureConfiguration.product_id == product_id,
            ProcedureConfiguration.product_version == product_version,
            ProcedureConfiguration.material_key == scope.material_key,
            ProcedureConfiguration.flow_node_id == flow_node_id,
        ).with_for_update()
    )
    if configuration is None:
        configuration = ProcedureConfiguration(
            product_id=product_id,
            product_version=product_version,
            material_key=scope.material_key,
            flow_node_id=flow_node_id,
        )
        session.add(configuration)
        session.flush()
    existing_prices = list(session.scalars(
        select(ProcedurePrice).where(
            ProcedurePrice.configuration_id == configuration.id,
        ).with_for_update()
    ))
    existing_by_procedure = {item.procedure_id: item for item in existing_prices}
    if configuration.confirmed_at is not None:
        submitted_ids = {
            item.procedure_id for item in payload.procedures
            if item.procedure_id is not None
        }
        if (
            len(submitted_ids) != len(payload.procedures)
            or submitted_ids != set(existing_by_procedure)
        ):
            raise DomainError(
                "procedure_configuration_locked",
                "工艺配置已确认，不能修改工艺清单",
                status_code=409,
            )
    retained_ids: set[int] = set()
    for name, (procedure_id, unit_price) in normalized.items():
        procedure = resolve_workshop_procedure(
            session,
            workshop_id=scope.workshop_id,
            procedure_id=procedure_id,
            procedure_name=name if procedure_id is None else None,
            required_input_mode=scope.expected_input_mode,
        )
        if (
            procedure.workshop_id != scope.workshop_id
            or procedure.procedure_name != name
        ):
            raise DomainError("procedure_workshop_invalid", "所选工艺不属于当前车间")
        retained_ids.add(procedure.id)
        price = existing_by_procedure.get(procedure.id)
        if price is None:
            price = ProcedurePrice(
                configuration_id=configuration.id,
                procedure_id=procedure.id, unit_price=unit_price,
            )
            session.add(price)
            session.flush()
            _record_price_revision(
                session,
                department_id=scope.department_id,
                target_type="formal",
                target_id=price.id,
                target_label=f"{scope.target_prefix} · {procedure.procedure_name}",
                previous_unit_price=None,
                new_unit_price=unit_price,
                actor_username=actor_username,
            )
        else:
            _record_price_revision(
                session,
                department_id=scope.department_id,
                target_type="formal",
                target_id=price.id,
                target_label=f"{scope.target_prefix} · {procedure.procedure_name}",
                previous_unit_price=price.unit_price,
                new_unit_price=unit_price,
                actor_username=actor_username,
            )
            price.unit_price = unit_price
    for price in existing_prices:
        if price.procedure_id in retained_ids:
            continue
        if has_standard_execution_order(
            session,
            product_id=product_id,
            product_version=product_version,
            origin_flow_node_id=origin_flow_node_id,
            flow_node_id=flow_node_id,
            procedure_id=price.procedure_id,
        ):
            raise DomainError("procedure_referenced", "已被工单引用的工艺不能删除")
        procedure_id = price.procedure_id
        procedure_name = next(
            (
                item.procedure_name
                for item in get_department_procedure_routes(session, scope.department_id)
                if item.id == procedure_id
            ),
            str(procedure_id),
        )
        _record_price_revision(
            session,
            department_id=scope.department_id,
            target_type="formal",
            target_id=price.id,
            target_label=f"{scope.target_prefix} · {procedure_name}",
            previous_unit_price=price.unit_price,
            new_unit_price=None,
            actor_username=actor_username,
        )
        session.delete(price)
        session.flush()
        has_price = session.scalar(
            select(ProcedurePrice.id)
            .where(ProcedurePrice.procedure_id == procedure_id)
            .limit(1)
        )
        if (
            has_price is None
            and not has_work_order_for_procedure(session, procedure_id)
        ):
            delete_procedure(session, procedure_id)
    if confirm:
        if configuration.confirmed_at is not None:
            raise DomainError(
                "procedure_configuration_already_confirmed",
                "工艺配置已经确认",
                status_code=409,
            )
        if not retained_ids:
            raise DomainError(
                "procedure_configuration_empty",
                "至少配置一个工艺后才能确认",
            )
        session.flush()
        configuration.confirmed_at = utc_now()
        configuration.confirmed_by = actor_username
