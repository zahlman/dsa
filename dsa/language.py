from .disassembly import Disassembler
from .filters import FilterLibrary
from .ui.location import folder
from .ui.tracing import my_tracer
from .ui.usefiles import fixed_roots
from .parsing.file_parsing import load_files, load_files_into, load_lines
from .parsing.path_loader import PathLoader
from .parsing.source_loader import SourceLoader
from .parsing.structgroup_loader import StructGroupLoader
from .parsing.type_loader import TypeLoader
from .plugins import is_function, load_plugins


_DEFAULT_PATHS = [
    # Default to including all system modules and nothing user-defined.
    'interpreters',
    '    **',
    'types',
    '    **',
    'structgroups',
    '    **',
    'filters',
    '    **'
]


def _load_paths(pathfile):
    roots = fixed_roots()
    return (
        load_lines(_DEFAULT_PATHS, PathLoader, roots, None)
        if pathfile is None
        else load_files([pathfile], PathLoader, roots, folder(pathfile))
    )


_INTERPRETER_SPEC = {
    'assemble': is_function,
    'disassemble': is_function,
    'item_size': is_function
}


def _load(paths):
    with my_tracer('Loading interpreters'):
        interpreters = load_plugins(paths['interpreters'], _INTERPRETER_SPEC)
    with my_tracer('Loading types'):
        type_data = load_files(paths['types'], TypeLoader)
    with my_tracer('Loading structgroups'):
        load_files_into(
            interpreters, paths['structgroups'], StructGroupLoader, *type_data
        )
    with my_tracer('Loading filters'):
        filters = FilterLibrary(paths['filters'])
    return Language(interpreters, filters)


class Language:
    def __init__(self, interpreters, filters):
        self._interpreters = interpreters
        self._filters = filters


    @staticmethod
    @my_tracer('Loading language')
    def load(pathfile):
        with my_tracer('Loading definition paths'):
            paths = _load_paths(pathfile)
        return _load(paths)


    def assemble(self, source):
        return load_files(
            [source], SourceLoader, self._interpreters, self._filters
        )


    # TODO fix this interface
    def disassemble(self, data, group_name, position, output):
        Disassembler(
            data, self._interpreters, self._filters, group_name, position
        )(output)
