# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

from .file_parsing import SimpleLoader
from .line_parsing import line_parser
from .token_parsing import single_parser
from ..errors import UserError
from ..ui.tracing import my_tracer
from functools import partial
from glob import glob
from os.path import join as join_path, abspath as fix_path


class INNER_STAR(UserError):
    """`*` not allowed as a module path component"""


class INNER_DOUBLE_STAR(UserError):
    """`**` not allowed in the middle of a module path"""


class FLOATING_MODULE(UserError):
    """module path outside of path block"""


_PATH_TYPES = {
    'types': 'txt',
    'structgroups': 'txt',
    'filters': 'py',
    'interpreters': 'py'
}


_section_parser = line_parser(
    'path group',
    single_parser('path type', set(_PATH_TYPES.keys())),
    single_parser('root path', 'string?'),
    required=1
)


class PathLoader(SimpleLoader):
    def __init__(self, system_roots, config_root):
        self._roots = None
        self._kind = None
        self._system_roots = system_roots
        self._config_root = config_root
        self._accumulator = {k: set() for k in _PATH_TYPES.keys()}


    def unindented(self, tokens):
        kind, root = _section_parser(tokens)
        if root is None:
            roots = [
                fix_path(join_path(r, kind))
                for r in self._system_roots
            ]
        else:
            roots = [
                fix_path(join_path(self._config_root, root))
            ]
        self._roots = roots
        self._kind = kind


    def indented(self, tokens):
        FLOATING_MODULE.require(self._kind is not None)
        pathdict = self._accumulator[self._kind]
        *parts, last = [
            single_parser('path component', 'string')(t)
            for t in tokens
        ]
        INNER_STAR.require('*' not in parts)
        INNER_DOUBLE_STAR.require('**' not in parts)
        ext = _PATH_TYPES[self._kind]
        if last == '*':
            last = [f'*.{ext}']
        elif last == '**':
            last = ['**', f'*.{ext}']
        else:
            last = [f'{last}.{ext}']
        added = False
        relative_pattern = join_path(*parts, *last)
        for root in self._roots:
            pattern = join_path(root, relative_pattern)
            my_tracer.trace(f'Collecting: {pattern}')
            for path in glob(pattern, recursive=True):
                pathdict.add(fix_path(path))
                added = True
        if not added:
            my_tracer.trace(
                f'Warning: pattern `{relative_pattern}` found no files'
            )


    def result(self):
        return self._accumulator
