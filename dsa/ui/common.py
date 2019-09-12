from ..parsing.file_parsing import load_files, load_files_new, load_files_tagged, load_lines, load_lines_new # FIXME 
from ..parsing.path_loader import PathLoader
from ..parsing.structgroup_loader import resolve_structgroup, StructGroupLoader
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
    setup = PathLoader.create_with_accumulator
    return (
        load_lines_new(_DEFAULT_PATHS, setup, root, root)
        if pathfile is None
        else load_files_new([pathfile], setup, root, folder(pathfile))
    )


@timed('Loading types...')
def _load_types(paths):
    return resolve_types(
        load_files_new(paths['types'], TypeLoader.create_with_accumulator)
    )


@timed('Loading structgroups...')
def _load_structgroups(types, paths):
    return {
        name: resolve_structgroup(group)
        for name, group in load_files_tagged(
            paths['structgroups'],
            StructGroupLoader.create_with_accumulator,
            types
        ).items()
    }


@timed('Loading language...')
def load_language(pathfile):
    paths = _load_paths(pathfile)
    return _load_structgroups(_load_types(paths), paths)
