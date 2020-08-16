# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

from ..errors import UserError
from ..filters import FilterLibrary
from ..parsing.file_parsing import load_files, load_files_into, load_lines
from ..parsing.path_loader import PathLoader
from ..parsing.structgroup_loader import StructGroupLoader
from ..parsing.type_loader import TypeLoader
from ..plugins import is_function, load_plugins
from .entrypoint import rebind
from .tracing import timed, tracing
from .location import folder
from .usefiles import fixed_roots
from contextlib import contextmanager
from datetime import datetime
from functools import partial, wraps
import sys, traceback


"""Common loading routines for dsa and dsd."""


@timed('Loading binary...')
def get_data(source):
    with open(source, 'rb') as f:
        return f.read()


_DEFAULT_PATHS = [
    # Default to including all system modules and nothing user-defined.
    'types',
    '    **',
    'structgroups',
    '    **',
    'filters',
    '    **',
    'interpreters',
    '    **'
]


@timed('Loading definition paths...')
def _load_paths(pathfile):
    roots = fixed_roots()
    return (
        load_lines(_DEFAULT_PATHS, PathLoader, roots, None)
        if pathfile is None
        else load_files([pathfile], PathLoader, roots, folder(pathfile))
    )


@timed('Loading filters...')
def _load_filters(paths):
    return FilterLibrary(paths['filters'])


@timed('Loading types...')
def _load_types(paths):
    return load_files(paths['types'], TypeLoader)


@timed('Loading structgroups...')
def _load_structgroups(interpreters, enums, types, paths):
    load_files_into(
        interpreters, paths['structgroups'], StructGroupLoader, enums, types
    )


@timed('Loading interpreters...')
def _load_interpreters(paths):
    method_names = '__init__', 'assemble', 'disassemble', 'item_size'
    property_names = 'alignment',
    return load_plugins(
        paths['interpreters'], {
            'assemble': is_function,
            'disassemble': is_function,
            'item_size': is_function
        }
    )


@timed('Loading language...')
def load_language(pathfile):
    paths = _load_paths(pathfile)
    interpreters = _load_interpreters(paths)
    enums, types = _load_types(paths)
    _load_structgroups(interpreters, enums, types, paths)
    filters = _load_filters(paths)
    return interpreters, filters


def _errmsg(e):
    print(e, file=sys.stderr)


@contextmanager
def _fail():
    tracing(False) # Otherwise, one 'Done' message may escape.
    # flush to ensure serial output when stdout is available.
    sys.stdout.flush()
    _errmsg(' OOPS '.center(58, '-')) # Always show this message.
    yield
    # flush again to be nice to any subsequent calls, if we're being
    # invoked programmatically rather than from the command line.
    sys.stderr.flush()


def _crash(e, tb):
    now = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
    filename = f'dsalog-{now}.txt'
    _errmsg('DSA encountered an internal error and must abort:')
    _errmsg(e)
    try:
        with open(filename, 'w') as f:
            f.writelines(tb)
    except Exception as e:
        _errmsg('DSA tried but failed to produce an error report. Sorry. :(')
    else:
        _errmsg(f'A log was be saved to {filename}.')
        _errmsg(f'Please submit it when reporting errors.')


def _io_error(e):
    _errmsg('DSA encountered a problem with reading or writing a file:')
    _errmsg(e)
    _errmsg('Please make sure that the path is correct and nothing is')
    _errmsg('trying to use the file at the same time as DSA. Aborting.')


def _user_error(e):
    _errmsg('DSA encountered an error in the data:')
    _errmsg(f'{e.__class__.__name__}: {e}')
    _errmsg('Aborting.')


def _report(func, *args, **kwargs):
    try:
        func(*args, **kwargs)
    except Exception as e:
        with _fail():
            if isinstance(e, IOError):
                _io_error(e)
            elif isinstance(e, UserError):
                _user_error(e)
            else:
                _crash(e, traceback.format_exc())


def reporting(label):
    # You are not expected to understand this.
    return lambda f: rebind(f, wraps(f)(partial(timed(label)(_report), f)))
