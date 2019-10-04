from .errors import wrap as wrap_errors, MappingError, UserError
from .parsing.line_parsing import line_parser, output_line
from .parsing.token_parsing import single_parser
from .plugins import load_plugins


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


class _DummyView:
    def __init__(self, source, location):
        self._source = source
        self._location = location


    def get(self, offset, size):
        source, start = self._source, self._location + offset
        return source[start:] if size is None else source[start:start+size]


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
        output_line(outfile, [f'@{self._name}'], *self._view.params(size))
        self._next.write_params(size, outfile)


class FilterLibrary:
    def __init__(self, paths):
        self._filters = load_plugins(
            paths, 'pack', ('View', ('__init__', 'get', 'params'), ())
        )


    def view(self, name, base_get, tokens):
        pack, view = UNKNOWN_FILTER.get(self._filters, name)
        return VIEW_CREATION_FAILED.convert(
            Exception, view, base_get, tokens
        )


    def pack(self, data, name, tokens):
        pack, view = UNKNOWN_FILTER.get(self._filters, name)
        return PACK_FAILED.convert(
            Exception, wrap_errors, f'Filter `{name}`', pack, data, tokens
        )


    def chain(self, specs, source, location):
        return (
            _ViewChain(self, specs, source, location)
            if specs
            else _DummyView(source, location)
        )
