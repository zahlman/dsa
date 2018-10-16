from functools import lru_cache
from importlib.util import spec_from_file_location, module_from_spec
import os


@lru_cache(None)
def dynamic_import(folder, name):
    path = os.path.join(folder, f'{name}.py')
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
