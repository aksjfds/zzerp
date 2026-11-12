from modules.contracts import ModuleDescriptor


MODULE = ModuleDescriptor(
    name="identity",
    public_api="modules.identity.api",
    owns=("users", "user_sessions", "authentication", "authorization"),
    collaboration_apis=("modules.identity.read_api",),
)
