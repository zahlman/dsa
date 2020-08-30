# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

from .file_parsing import SimpleLoader
from .line_parsing import line_parser
from .token_parsing import single_parser
from ..errors import MappingError, UserError


class BAD_CODEC_TYPENAME(MappingError):
    """`{key}` is not the name of a valid codec loader"""


class DUPLICATE_CODEC(MappingError):
    """Already have a codec named `{key}`"""


class NO_SECTION_HEADER(UserError):
    """codec data appeared before meta line"""


_parse_meta = line_parser(
    'codec metadata line',
    single_parser('codec name', 'string'),
    single_parser('codec type', 'string')
)


class CodecLoader(SimpleLoader):
    def __init__(self, subloaders):
        self._subloaders = subloaders
        self._results = {}
        self._current_name = None
        self._current_subloader = None


    def meta(self, tokens):
        if self._current_subloader is not None:
            DUPLICATE_CODEC.add_unique(
                self._results,
                self._current_name, self._current_subloader.result()
            )
        self._current_name, subloader_name = _parse_meta(tokens)
        self._current_subloader = BAD_CODEC_TYPENAME.get(
            self._subloaders, subloader_name
        ).Loader()


    def unindented(self, tokens):
        NO_SECTION_HEADER.require(self._current_subloader is not None)
        self._current_subloader.line(tokens)
    indented = unindented


    def result(self):
        if self._current_subloader is not None:
            DUPLICATE_CODEC.add_unique(
                self._results,
                self._current_name, self._current_subloader.result()
            )
        return self._results
