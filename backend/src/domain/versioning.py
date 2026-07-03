from domain.enums import MasterDataStatus


ALLOWED_VERSION_TRANSITIONS: dict[MasterDataStatus, set[MasterDataStatus]] = {
    MasterDataStatus.DRAFT: {MasterDataStatus.PUBLISHED},
    MasterDataStatus.PUBLISHED: {MasterDataStatus.INACTIVE},
    MasterDataStatus.INACTIVE: set(),
}


def can_transition_version(
    current: MasterDataStatus,
    target: MasterDataStatus,
) -> bool:
    return target in ALLOWED_VERSION_TRANSITIONS[current]
