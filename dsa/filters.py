from .errors import wrap as wrap_errors, MappingError, UserError
from .parsing.line_parsing import line_parser
from .parsing.token_parsing import single_parser
from .plugins import exists, is_class_with, is_function, is_method, is_property, load_plugins


class UNKNOWN_FILTER(MappingError):
    """unknown filter `{key}`"""


class VIEW_CREATION_FAILED(UserError):
    """could not create a view with {name} filter"""


class PACK_FAILED(UserError):
    """packing failed: {reason}"""


def _load_unpacked_data(cls, data, params):
    # Capture UserErrors in either the constructor or the property.
    view = cls(data, *params)
    return view, view.data


class _UnpackChain:
    def __init__(self, binary, offset, unpackers):
        # Chunk reading is initially unlimited from the `offset` point.
        data = memoryview(binary)[offset:]
        self._views = []
        # First view is the first listed in the chain, and first that
        # appears in the data description. We unpack data in this order.
        for name, cls, params in unpackers:
            view, data = wrap_errors(
                f'Filter `{name}`', _load_unpacked_data, cls, data, params
            )
            self._views.append((name, view))
        self._data = data # result of the last step.


    @property
    def data(self):
        return self._data


    def tokens(self, size):
        # Data will be packed in the reverse order, so we need to iterate
        # in reverse to propagate the packed sizes. But the resulting list
        # needs to be in the same order as the views, so we prepend.
        lines = []
        for name, view in reversed(self._views):
            line = ['!', (name,)]
            size, tokens = wrap_errors(
                f'Filter `{name}`', view.pack_params, size
            )
            line.extend(tokens)
            lines.insert(0, line)
        # FIXME: use `size`.
        return lines


# Given a line of filter info from the `pointer` in a type description,
# this parser gets the filter name and unparsed View constructor parameters.
_spec_parser = line_parser(
    'filter specification',
    single_parser('name', 'string'),
    more=True
)


# create a parser for View constructor parameters or pack_args parameters.
def _build_parser(name, args):
    return line_parser(
        f'`{name}` filter parameters',
        *map(single_parser, args[::2], args[1::2])
    )


class FilterLibrary:
    def __init__(self, paths):
        self._filters = load_plugins(
            paths, {
                'pack': is_function,
                'pack_args': exists,
                'View': (is_class_with, {
                    'data': is_property, 'pack_params': is_method
                }),
                'unpack_args': exists
            }
        )


    def pack_all(self, data, specs):
        for name, params in reversed(specs):
            module = UNKNOWN_FILTER.get(self._filters, name)
            data = wrap_errors(
                f'Filter `{name}`', module.pack, data,
                *_build_parser(name, module.pack_args)(params)
            )
        # Enforce that pack() functions do the right thing.
        assert isinstance(data, bytes)
        return data


    def _unpacker(self, name, params):
        module = UNKNOWN_FILTER.get(self._filters, name)
        parser = _build_parser(name, module.unpack_args)(params)
        return name, module.View, parser


    def unpack_chain(self, binary, offset, specs):
        return _UnpackChain(
            binary, offset,
            [self._unpacker(*_spec_parser(spec)) for spec in specs]
        )
