from modules.contracts import ModuleDescriptor

MODULE = ModuleDescriptor(
    name="organization",
    public_api="modules.organization.api",
    owns=("production_department",),
    collaboration_apis=("modules.organization.read_api",),
)
