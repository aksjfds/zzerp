"""Narrow configuration contract used by planning and work-order orchestration."""

from collections.abc import Collection
from dataclasses import dataclass

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from modules.errors import DomainError
from modules.organization.model_api import Department, Procedure, Workshop
from modules.organization.transaction_api import resolve_workshop_procedure
from modules.standard_execution.persistence import (
    ProcedureConfiguration,
    ProcedurePrice,
)


ProcedureConfigurationScope = tuple[int, int, str, str]


@dataclass(frozen=True, slots=True)
class ConfiguredProcedure:
    id: int
    workshop_id: int
    department_name: str
    department_code: str
    procedure_name: str


def list_confirmed_procedures(
    session: Session,
    scopes: Collection[ProcedureConfigurationScope],
) -> dict[ProcedureConfigurationScope, list[ConfiguredProcedure]]:
    unique_scopes = set(scopes)
    if not unique_scopes:
        return {}
    configurations = list(session.scalars(
        select(ProcedureConfiguration).where(
            tuple_(
                ProcedureConfiguration.product_id,
                ProcedureConfiguration.product_version,
                ProcedureConfiguration.material_key,
                ProcedureConfiguration.flow_node_id,
            ).in_(unique_scopes),
            ProcedureConfiguration.confirmed_at.is_not(None),
        )
    ))
    result = {
        _scope(configuration): [] for configuration in configurations
    }
    if not configurations:
        return result
    configuration_by_id = {item.id: item for item in configurations}
    rows = session.execute(
        select(ProcedurePrice.configuration_id, Procedure, Workshop, Department)
        .join(Procedure, Procedure.id == ProcedurePrice.procedure_id)
        .join(Workshop, Workshop.id == Procedure.workshop_id)
        .join(Department, Department.id == Workshop.department_id)
        .where(ProcedurePrice.configuration_id.in_(configuration_by_id))
        .order_by(ProcedurePrice.id)
    )
    for configuration_id, procedure, workshop, department in rows:
        result[_scope(configuration_by_id[configuration_id])].append(
            ConfiguredProcedure(
                id=procedure.id,
                workshop_id=workshop.id,
                department_name=department.department_name,
                department_code=department.department_code,
                procedure_name=procedure.procedure_name,
            )
        )
    return result


def resolve_work_order_procedure(
    session: Session,
    *,
    scope: ProcedureConfigurationScope,
    workshop_id: int,
    procedure_id: int | None,
    procedure_name: str | None,
    is_temporary: bool,
    required_input_mode: str,
):
    configuration = session.scalar(
        select(ProcedureConfiguration).where(
            ProcedureConfiguration.product_id == scope[0],
            ProcedureConfiguration.product_version == scope[1],
            ProcedureConfiguration.material_key == scope[2],
            ProcedureConfiguration.flow_node_id == scope[3],
            ProcedureConfiguration.confirmed_at.is_not(None),
        ).with_for_update()
    )
    if configuration is None:
        raise DomainError(
            "procedure_configuration_not_confirmed",
            "当前物料和车间尚未确认工艺配置",
            status_code=409,
        )
    configured_ids = set(session.scalars(
        select(ProcedurePrice.procedure_id).where(
            ProcedurePrice.configuration_id == configuration.id
        )
    ))
    if is_temporary:
        if procedure_id is not None or not (procedure_name or "").strip():
            raise DomainError("temporary_procedure_required", "请填写临时工艺名称")
        procedure = resolve_workshop_procedure(
            session,
            workshop_id=workshop_id,
            procedure_id=None,
            procedure_name=procedure_name,
            required_input_mode=required_input_mode,
        )
        if procedure.id in configured_ids:
            raise DomainError(
                "temporary_procedure_is_configured",
                "该工艺已在正式配置中，请创建普通工单",
                status_code=409,
            )
        return procedure
    if procedure_id is None or (procedure_name or "").strip():
        raise DomainError("configured_procedure_required", "请选择已配置工艺")
    if procedure_id not in configured_ids:
        raise DomainError(
            "work_order_procedure_not_configured",
            "所选工艺不在已确认配置中",
            status_code=409,
        )
    return resolve_workshop_procedure(
        session,
        workshop_id=workshop_id,
        procedure_id=procedure_id,
        procedure_name=None,
        required_input_mode=required_input_mode,
    )


def _scope(configuration: ProcedureConfiguration) -> ProcedureConfigurationScope:
    return (
        configuration.product_id,
        configuration.product_version,
        configuration.material_key,
        configuration.flow_node_id,
    )


__all__ = [
    "ConfiguredProcedure",
    "ProcedureConfigurationScope",
    "list_confirmed_procedures",
    "resolve_work_order_procedure",
]
