# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

from .catalog import PathSearcher
from .codecs import make_codec_library
from .disassembly import Disassembler
from .filters import FilterLibrary
from .ui.tracing import my_tracer
from .parsing.file_parsing import load_files, load_files_into
from .parsing.source_loader import SourceLoader
from .parsing.structgroup_loader import StructGroupLoader
from .parsing.type_loader import TypeLoader
from .plugins import is_function, load_plugins
from pathlib import Path


@my_tracer('Loading interpreters')
def _interpreters(get_paths):
    with my_tracer('Loading native-code interpreters'):
        interpreters = load_plugins(get_paths('interpreters'), {
            'assemble': is_function,
            'disassemble': is_function,
            'item_size': is_function
        })
    with my_tracer('Loading types'):
        type_data = load_files(get_paths('types'), TypeLoader)
    with my_tracer('Loading structgroup-based interpreters'):
        load_files_into(
            interpreters, get_paths('structgroups'),
            StructGroupLoader, *type_data
        )
    return interpreters


@my_tracer('Loading filters')
def _filters(get_paths):
    return FilterLibrary(get_paths('filters'))


@my_tracer('Loading codecs')
def _codecs(get_paths):
    return make_codec_library(get_paths('codec_code'), get_paths('codec_data'))


class Language:
    def __init__(self, interpreters, filters, codecs):
        self._interpreters = interpreters
        self._filters = filters
        self._codecs = codecs


    @staticmethod
    @my_tracer('Loading language')
    def create(libraries, paths, target):
        with my_tracer('Loading definition paths'):
            search = PathSearcher.create(libraries, paths, target)
        return Language(
            _interpreters(search), _filters(search), _codecs(search)
        )


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
