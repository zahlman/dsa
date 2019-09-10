from ..errors import UserError
from .line_parsing import TokenError
from glob import glob
import os.path


class UNKNOWN_ROOT(TokenError):
    """unindented line should start with `types` or `structgroups`"""


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


class PathLoader:
    def __init__(self, system_root, config_root):
        self._system_root = system_root
        self._config_root = config_root
        self._reset()


    def _reset(self):
        self._paths = {'types': set(), 'structgroups': set()}
        self._root = None
        self._kind = None


    def add_line(self, indent, line_tokens):
        if indent:
            self._add_path(line_tokens)
        else:
            self._setup(line_tokens)


    def _setup(self, line_tokens):
        kind, root = JUNK_ROOT.pad(line_tokens, 1, 2)
        kind = JUNK_ROOT.singleton(kind)
        root = JUNK_ROOT.singleton(root)
        if root is None:
            root = os.path.join(self._system_root, kind)
        else:
            root = os.path.join(self._config_root, root)
        UNKNOWN_ROOT.require(kind in self._paths.keys())
        self._kind = kind
        self._root = root


    def _add_path(self, line_tokens):
        FLOATING_MODULE.require(self._kind is not None)
        *parts, last = [
            INVALID_PATH_COMPONENT.pad(t, 1, 1)[0]
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
            self._paths[self._kind].add(os.path.realpath(path))


    def end_file(self, label, accumulator):
        for key, value in self._paths.items():
            accumulator.setdefault(key, []).extend(value)
        self._reset()
