from ..errors import UserError
from .line_parsing import one_of, TokenError
from functools import partial
from glob import glob
import os.path


class JUNK_ROOT(TokenError):
    """junk data after root path"""


class INVALID_PATH_COMPONENT(TokenError):
    """module path components must not have `:`/`,`"""


class BAD_PATH(UserError):
    """indented line should be a single token, and specify a dotted path optionally ending in * or **"""


class INNER_STAR(UserError):
    """`*` not allowed as a module path component"""


class INNER_DOUBLE_STAR(UserError):
    """`**` not allowed in the middle of a module path"""


class FLOATING_MODULE(UserError):
    """module path outside of `types`/`structs` block"""


_PATH_TYPES = ('types', 'structgroups')


class _PathLoader:
    def __init__(self, system_root, config_root):
        self._root = None
        self._kind = None
        self._system_root = system_root
        self._config_root = config_root


    def _setup(self, line_tokens):
        kind, root = JUNK_ROOT.pad(line_tokens, 1, 2)
        kind = one_of(*_PATH_TYPES)(kind)
        root = JUNK_ROOT.singleton(root)
        if root is None:
            root = os.path.join(self._system_root, kind)
        else:
            root = os.path.join(self._config_root, root)
        self._root = root
        self._kind = kind


    def _add_path(self, accumulator, line_tokens):
        FLOATING_MODULE.require(self._kind is not None)
        pathdict = accumulator[self._kind]
        *parts, last = [
            INVALID_PATH_COMPONENT.singleton(t)
            for t in line_tokens
        ]
        INNER_STAR.require('*' not in parts)
        INNER_DOUBLE_STAR.require('**' not in parts)
        if last == '*':
            last = ['*.txt']
        elif last == '**':
            last = ['**', '*.txt']
        else:
            last = [f'{last}.txt']
        pattern = os.path.join(self._root, *parts, *last)
        for path in glob(pattern, recursive=True):
            pathdict.add(os.path.realpath(path))


    def __call__(self, accumulator, indent, line_tokens):
        if indent:
            self._add_path(accumulator, line_tokens)
        else:
            self._setup(line_tokens)


def PathLoader(system_root, config_root):
    accumulator = {k: set() for k in _PATH_TYPES}
    return _PathLoader(system_root, config_root), accumulator
