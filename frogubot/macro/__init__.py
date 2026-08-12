from .storage import MacroStorage
from .server_storage import ServerMacroStorage
from .engine import build_context, select_macros, test_macro


def register_macro_handlers(*args, **kwargs):
    from .builder import register_macro_handlers as _register_macro_handlers

    return _register_macro_handlers(*args, **kwargs)
