from modules.engineering.descriptor import MODULE as ENGINEERING
from modules.organization.descriptor import MODULE as ORGANIZATION
from modules.identity.descriptor import MODULE as IDENTITY
from modules.planning.descriptor import MODULE as PLANNING
from modules.sales.descriptor import MODULE as SALES


MODULES = {
    module.name: module
    for module in (
        IDENTITY,
        ORGANIZATION,
        ENGINEERING,
        SALES,
        PLANNING,
    )
}


def module_descriptor(name: str):
    try:
        return MODULES[name]
    except KeyError as exc:
        raise LookupError(f"Unknown business module: {name}") from exc


def module_manifests() -> list[dict]:
    return [
        {
            "name": module.name,
            "api_version": module.api_version,
            "public_api": module.public_api,
            "collaboration_apis": list(module.collaboration_apis),
            "owns": list(module.owns),
            "collaborates_with": list(module.collaborates_with),
        }
        for module in MODULES.values()
    ]
