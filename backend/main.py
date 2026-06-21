from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


BACKEND_SRC = Path(__file__).resolve().parent / "src"
BACKEND_MAIN = BACKEND_SRC / "main.py"

if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

spec = spec_from_file_location("zzerp_backend_main", BACKEND_MAIN)
if spec is None or spec.loader is None:
    raise RuntimeError("Unable to load backend application")

module = module_from_spec(spec)
spec.loader.exec_module(module)
app = module.app
