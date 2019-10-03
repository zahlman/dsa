from .errors import wrap, MappingError, UserError
from .parsing.line_parsing import format_line, line_parser
from .parsing.token_parsing import single_parser
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
    """`{module_name}.View` doesn't have a method named `{attr}`"""


class UNKNOWN_FILTER(MappingError):
    """unknown filter `{key}`"""


class VIEW_CREATION_FAILED(UserError):
    """could not create a view with {name} filter"""


class PACK_FAILED(UserError):
    """packing failed: {reason}"""


_spec_parser = line_parser(
    'filter specification',
    single_parser('name', 'string'),
    more=True
)


def _filter_from_module(module_name, module):
    cls = NO_VIEW_IN_MODULE.get(module, 'View', module_name=module_name)
    pack = NO_PACK_IN_MODULE.get(module, 'pack', module_name=module_name)
    VIEW_NOT_CLASS.require(isclass(cls), module_name=module_name)
    PACK_NOT_CALLABLE.require(callable(pack), module_name=module_name)
    for name in ('__init__', 'get', 'params'):
        method = MISSING_METHOD.get(cls, name, module_name=module_name)
        MISSING_METHOD.require(
            callable(method), attr=name, module_name=module_name
        )
    return cls, pack


def _filter_from_path(path):
    trace(f"Loading: File '{path}'")
    folder, filename = os.path.split(path)
    basename, extension = os.path.splitext(filename)
    spec = spec_from_file_location(basename, path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return basename, _filter_from_module(basename, module)


class _DummyView:
    def __init__(self, source, location):
        self._source = source
        self._location = location


    def get(self, offset, size):
        start = self._location + offset
        return self._source[start:start+size]


    def write_params(self, size, outfile):
        pass


class _ViewChain:
    def __init__(self, library, specs, source, location):
        my_spec, *specs = specs
        name, params = _spec_parser(my_spec)
        self._next = library.chain(specs, source, location)
        self._view = library.view(name, self._next.get, params)
        self._name = name


    @property
    def get(self):
        """The data accessor for the topmost filter."""
        return self._view.get


    def write_params(self, size, outfile):
        tokens = f'@{self._name}', *self._view.params(size)
        for wrapped in format_line(tokens):
            outfile.write(wrapped + '\n')
        self._next.write_params(size, outfile)


class FilterLibrary:
    def __init__(self, paths):
        self._filters = dict(
            wrap(path, _filter_from_path, path)
            for path in paths
        )


    def view(self, name, base_get, tokens):
        cls, pack = UNKNOWN_FILTER.get(self._filters, name)
        return VIEW_CREATION_FAILED.convert(
            Exception, cls, base_get, tokens
        )


    def pack(self, data, name, tokens):
        cls, pack = UNKNOWN_FILTER.get(self._filters, name)
        return PACK_FAILED.convert(
            Exception, wrap, f'Filter {name}', pack, data, tokens
        )


    def chain(self, specs, source, location):
        return (
            _ViewChain(self, specs, source, location)
            if specs
            else _DummyView(source, location)
        )
