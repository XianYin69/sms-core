# -*- coding: utf-8 -*-
"""task_table re-export: real codec is sub_skills/task_table/task_table.py.

The shim only prepends the sub_skills dir and swaps itself in sys.modules for
the real module, so every `import task_table` in the process returns the same live
module object that the real codec uses internally (test monkeypatches and
call-sites land on one object, and internal cross-references stay intact).
"""
import importlib.util as _ilu
import os
import sys as _sys

_sys_path = os.path.join(os.path.dirname(__file__), '..', '..', 'sub_skills', 'task_table')
_src = os.path.join(_sys_path, 'task_table.py')
if os.path.isfile(_src):
    if _sys_path not in _sys.path:
        _sys.path.insert(0, _sys_path)
    _spec = _ilu.spec_from_file_location(__name__, _src)
    _mod = _ilu.module_from_spec(_spec)
    _sys.modules[__name__] = _mod
    _spec.loader.exec_module(_mod)
    # importlib's _load() pops sys.modules[name] for the cache; once the real
    # module object is registered here under this name, later imports return it.
    _sys.modules[__name__] = _mod
else:
    from task_table import *  # noqa: F401,F403
