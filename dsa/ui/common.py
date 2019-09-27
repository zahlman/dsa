from ..filters import FilterLibrary
from ..parsing.file_parsing import load_files, load_files_tagged, load_lines
from ..parsing.path_loader import PathLoader
from ..parsing.structgroup_loader import StructGroupLoader
from ..parsing.type_loader import TypeLoader
from .tracing import timed
from .location import folder, get as get_location


"""Common loading routines for dsa and dsd."""


@timed('Loading binary...')
def get_data(source):
    with open(source, 'rb') as f:
        return f.read()


_DEFAULT_PATHS = [
    # Default to including all system modules and nothing user-defined.
    'types types',
    '    **',
    'structgroups structgroups',
    '    **',
    'filters filters',
    '    **'
]


@timed('Loading definition paths...')
def _load_paths(pathfile):
    root = get_location()
    return (
        load_lines(_DEFAULT_PATHS, PathLoader, root, root)
        if pathfile is None
        else load_files([pathfile], PathLoader, root, folder(pathfile))
    )


@timed('Loading filters...')
def _load_filters(paths):
    return FilterLibrary(paths['filters'])


@timed('Loading types...')
def _load_types(paths):
    return load_files(paths['types'], TypeLoader)


@timed('Loading structgroups...')
def _load_structgroups(types, paths):
    return load_files_tagged(paths['structgroups'], StructGroupLoader, types)


@timed('Loading language...')
def load_language(pathfile):
    paths = _load_paths(pathfile)
    groups = _load_structgroups(_load_types(paths), paths)
    filters = _load_filters(paths)
    return groups, filters
