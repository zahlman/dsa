from ..parsing.file_parsing import load_files, load_files_new, load_lines, load_lines_new # FIXME 
from ..parsing.path_loader import PathLoader
from ..parsing.structgroup_loader import StructGroupLoader
from ..parsing.type_loader import resolve_types, TypeLoader
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
    '    **'
]


@timed('Loading definition paths...')
def _load_paths(pathfile):
    root = get_location()
    if pathfile is None:
        return load_lines_new(_DEFAULT_PATHS, PathLoader, root, root)
    return load_files_new([pathfile], PathLoader, root, folder(pathfile))


@timed('Loading types...')
def _load_types(paths):
    return resolve_types(load_files_new(paths['types'], TypeLoader))


@timed('Loading structgroups...')
def _load_structgroups(types, paths):
    return load_files(StructGroupLoader(types), *paths['structgroups'])


@timed('Loading language...')
def load_language(pathfile):
    paths = _load_paths(pathfile)
    return _load_structgroups(_load_types(paths), paths)
