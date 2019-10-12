from ..filters import FilterLibrary
from ..parsing.file_parsing import load_files, load_files_into, load_lines
from ..parsing.path_loader import PathLoader
from ..parsing.structgroup_loader import StructGroupLoader
from ..parsing.type_loader import TypeLoader
from ..plugins import is_function, is_integer, load_plugins
from .tracing import timed
from .location import folder, get as get_location
from os.path import join as join_path, abspath as fix_path


"""Common loading routines for dsa and dsd."""


@timed('Loading binary...')
def get_data(source):
    with open(source, 'rb') as f:
        return f.read()


_DEFAULT_PATHS = [
    # Default to including all system modules and nothing user-defined.
    'types',
    '    **',
    'structgroups',
    '    **',
    'filters',
    '    **',
    'interpreters',
    '    **'
]


def library():
    return fix_path(join_path(get_location(), 'library'))


def extfile():
    return join_path(library(), 'libpaths.txt')


def roots():
    with open(extfile()) as f:
        return [path.strip() for path in f]


@timed('Loading definition paths...')
def _load_paths(pathfile):
    fixed_roots = [fix_path(join_path(library(), r)) for r in roots()]
    return (
        load_lines(_DEFAULT_PATHS, PathLoader, fixed_roots, None)
        if pathfile is None
        else load_files([pathfile], PathLoader, fixed_roots, folder(pathfile))
    )


@timed('Loading filters...')
def _load_filters(paths):
    return FilterLibrary(paths['filters'])


@timed('Loading types...')
def _load_types(paths):
    return load_files(paths['types'], TypeLoader)


@timed('Loading structgroups...')
def _load_structgroups(interpreters, enums, types, paths):
    load_files_into(
        interpreters, paths['structgroups'], StructGroupLoader, enums, types
    )


@timed('Loading interpreters...')
def _load_interpreters(paths):
    method_names = '__init__', 'assemble', 'disassemble', 'item_size'
    property_names = 'alignment',
    return load_plugins(
        paths['interpreters'], {
            'assemble': is_function,
            'disassemble': is_function,
            'item_size': is_function
        }
    )


@timed('Loading language...')
def load_language(pathfile):
    paths = _load_paths(pathfile)
    interpreters = _load_interpreters(paths)
    enums, types = _load_types(paths)
    _load_structgroups(interpreters, enums, types, paths)
    filters = _load_filters(paths)
    return interpreters, filters
