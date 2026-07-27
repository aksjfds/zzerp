"""Business modules for the zzerp modular monolith.

HTTP routers import ``modules.<name>.api``. Business modules may additionally
use collaboration ports ending in ``_api`` when the dependency is declared by
both module descriptors. Legacy top-level service, repository and model source
layers have been removed.
"""
