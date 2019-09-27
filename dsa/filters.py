from .errors import wrap, MappingError, UserError
from .ui.tracing import trace
from functools import partial
from importlib.util import spec_from_file_location, module_from_spec
import os


class NO_FILTER_IN_MODULE(UserError):
    """module doesn't define a Filter class"""


class BAD_FILTER_CLASS(UserError):
    """{name}.Filter is not a class or does not provide the expected methods"""


class UNKNOWN_FILTER(MappingError):
    """unknown filter `{key}`"""


class FILTER_LOADING_FAILED(UserError):
    """could not load filter"""


def _filter_class_from_path(path):
    trace(f"Loading: File '{path}'")
    folder, filename = os.path.split(path)
    basename, extension = os.path.splitext(filename)
    spec = spec_from_file_location(basename, path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    NO_FILTER_IN_MODULE.require(hasattr(module, 'Filter'))
    cls = module.Filter
    for required_method_name in ('__init__', 'pack', 'unpack'):
        BAD_FILTER_CLASS.require(
            hasattr(cls, required_method_name), name=basename
        )
    return basename, cls


def load_filter(lookup, name, params):
    cls = UNKNOWN_FILTER.get(lookup, name)
    return FILTER_LOADING_FAILED.convert(Exception, cls, *params)


def filter_library(paths):
    return partial(load_filter, dict(
        wrap(path, _filter_class_from_path, path)
        for path in paths
    ))
