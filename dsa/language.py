# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

from .codecs import make_codec_library
from .disassembly import Disassembler
from .filters import FilterLibrary
from .ui.tracing import my_tracer
from .ui.usefiles import fixed_roots
from .parsing.file_parsing import load_files, load_files_into, load_lines
from .parsing.path_loader import PathLoader
from .parsing.source_loader import SourceLoader
from .parsing.structgroup_loader import StructGroupLoader
from .parsing.type_loader import TypeLoader
from .plugins import is_function, load_plugins
from pathlib import Path


_DEFAULT_PATHS = [
    # Default to including all system modules and nothing user-defined.
    'interpreters',
    '    **',
    'types',
    '    **',
    'structgroups',
    '    **',
    'filters',
    '    **',
    'codec_code',
    '    **',
    'codec_data',
    '    **'
]


def _load_paths(pathfile):
    roots = fixed_roots()
    if pathfile is None:
        return load_lines(_DEFAULT_PATHS, PathLoader, roots, None)
    else:
        pathfile = Path(pathfile).absolute()
        return load_files([pathfile], PathLoader, roots, pathfile.parent)


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
    with my_tracer('Loading codecs'):
        codecs = make_codec_library(paths['codec_code'], paths['codec_data'])
    return Language(interpreters, filters, codecs)


class Language:
    def __init__(self, interpreters, filters, codecs):
        self._interpreters = interpreters
        self._filters = filters
        self._codecs = codecs


    @staticmethod
    @my_tracer('Loading language')
    def load(pathfile):
        with my_tracer('Loading definition paths'):
            paths = _load_paths(pathfile)
        return _load(paths)


    @staticmethod
    @my_tracer('Loading language')
    def from_catalog(catalog_dir, lib_names, target_name):
        with my_tracer('Loading definition paths'):
            paths = get_search_paths(catalog_dir, lib_names, target_name)
            resolve_paths = lambda kind: get_paths(paths, kind)
        with my_tracer('Loading interpreters'):
            interpreters = load_plugins(
                resolve_paths('interpreters'), _INTERPRETER_SPEC
            )
        with my_tracer('Loading types'):
            type_data = load_files(resolve_paths('types'), TypeLoader)
        with my_tracer('Loading structgroups'):
            load_files_into(
                interpreters, resolve_paths('structgroups'),
                StructGroupLoader, *type_data
            )
        with my_tracer('Loading filters'):
            filters = FilterLibrary(resolve_paths('filters'))
        with my_tracer('Loading codecs'):
            codecs = make_codec_library(
                resolve_paths('codec_code'), resolve_paths('codec_data')
            )
        return Language(interpreters, filters, codecs)


    def assemble(self, source):
        return load_files(
            [source], SourceLoader,
            self._interpreters, self._filters, self._codecs
        )


    # TODO fix this interface
    def disassemble(self, data, root_info, output):
        Disassembler(
            data, self._interpreters, self._filters, self._codecs, root_info
        )(output)
