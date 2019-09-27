from .errors import wrap, MappingError, UserError
from .ui.tracing import trace
from functools import partial
from importlib.util import spec_from_file_location, module_from_spec
from inspect import isclass
import os


class AttrError(UserError):
    @classmethod
    def get(cls, obj, attr, **kwargs):
        try:
            return getattr(obj, attr)
        except AttributeError:
            raise cls(attr=attr, **kwargs)


class NO_VIEW_IN_MODULE(AttrError):
    """`{module_name}` module doesn't define a `{attr}` class"""


class NO_PACK_IN_MODULE(AttrError):
    """`{module_name}` module doesn't define a `{attr}` function"""


class VIEW_NOT_CLASS(UserError):
    """`{module_name}.View` is not a class"""


class PACK_NOT_CALLABLE(UserError):
    """`{module_name}.pack` is not callable"""


class MISSING_METHOD(AttrError):
    """`{module_name}.View` is missing `{attr}` method"""


class NON_METHOD(UserError):
    """`{module_name}.View.{name}` is not callable"""


class UNKNOWN_FILTER(MappingError):
    """unknown filter `{key}`"""


class VIEW_CREATION_FAILED(UserError):
    """could not create a view with {name} filter"""


class PACK_FAILED(UserError):
    """packing failed: {reason}"""


def _filter_from_module(module_name, module):
    cls = NO_VIEW_IN_MODULE.get(module, 'View', module_name=module_name)
    pack = NO_PACK_IN_MODULE.get(module, 'pack', module_name=module_name)
    VIEW_NOT_CLASS.require(isclass(cls), module_name=module_name)
    PACK_NOT_CALLABLE.require(callable(pack), module_name=module_name)
    for name in ('__init__', 'get', 'params'):
        attr = MISSING_METHOD.get(cls, name, module_name=module_name)
        NON_METHOD.require(callable(attr), name=name, module_name=module_name)
    return cls, pack


def _filter_from_path(path):
    trace(f"Loading: File '{path}'")
    folder, filename = os.path.split(path)
    basename, extension = os.path.splitext(filename)
    spec = spec_from_file_location(basename, path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return basename, _filter_from_module(basename, module)


class FilterLibrary:
    def __init__(self, paths):
        self._filters = dict(
            wrap(path, _filter_from_path, path)
            for path in paths
        )


    def view(self, source, base, name, tokens):
        cls, pack = UNKNOWN_FILTER.get(self._filters, name)
        return VIEW_CREATION_FAILED.convert(
            Exception, cls, source, base, *tokens
        )


    def pack(self, data, name, tokens):
        cls, pack = UNKNOWN_FILTER.get(self._filters, name)
        return PACK_FAILED.convert(
            Exception, wrap, f'Filter {name}', pack, data, *tokens
        )
