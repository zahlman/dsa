from ..errors import UserError
from .file_parsing import SimpleLoader
from .line_parsing import TokenError
from .token_parsing import one_of, optional_string, string
from functools import partial
from glob import glob
import os.path


class BAD_ROOT(TokenError):
    """Invalid section header for path file"""


class INNER_STAR(UserError):
    """`*` not allowed as a module path component"""


class INNER_DOUBLE_STAR(UserError):
    """`**` not allowed in the middle of a module path"""


class FLOATING_MODULE(UserError):
    """module path outside of `types`/`structs` block"""


_PATH_TYPES = {
    'types': 'txt',
    'structgroups': 'txt',
    'filters': 'py'
}


class PathLoader(SimpleLoader):
    def __init__(self, system_root, config_root):
        self._root = None
        self._kind = None
        self._system_root = system_root
        self._config_root = config_root
        self._accumulator = {k: set() for k in _PATH_TYPES.keys()}


    def unindented(self, tokens):
        kind, root = BAD_ROOT.pad(tokens, 1, 2)
        kind = one_of(*_PATH_TYPES.keys())(kind, 'root path type')
        root = optional_string(root, 'root path')
        if root is None:
            root = os.path.join(self._system_root, kind)
        else:
            root = os.path.join(self._config_root, root)
        self._root = root
        self._kind = kind


    def indented(self, tokens):
        FLOATING_MODULE.require(self._kind is not None)
        pathdict = self._accumulator[self._kind]
        *parts, last = [
            string(t, 'path component')
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
        pattern = os.path.join(self._root, *parts, *last)
        for path in glob(pattern, recursive=True):
            pathdict.add(os.path.realpath(path))


    def result(self):
        return self._accumulator
