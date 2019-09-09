from ..assembly import SourceLoader
from ..disassembly import Disassembler
from ..file_parsing import load_files, load_lines
from ..path_loader import PathLoader
from ..structgroup_loader import StructGroupLoader
from ..type_loader import TypeLoader
from .diagnostic import timed, trace
import argparse, functools, os


def _invoke(func):
    # Use command-line arguments to call a function that was decorated
    # with `entry_point`, and possibly one or more `params`.
    func(**vars(func._parser.parse_args()))


def _setup(description, func):
    # implementation for `entry_point`.
    func._parser = argparse.ArgumentParser(
        prog=func.__name__, description=description
    )
    func.invoke = functools.partial(_invoke, func)
    return func


def _add_param(args, kwargs, func):
    *args, helptext = args
    func._parser.add_argument(*args, help=helptext, **kwargs)
    return func


def entry_point(description):
    """Set up a function for use as a CLI entry point by calling .invoke().
    This decorator must come after `param` decorators, but before anything
    that replaces the underlying function.
    The function will be called by parsing the command-line arguments into a
    Namespace, converting to a dict and splatting it out as kwargs."""
    return functools.partial(_setup, description)


def param(*args, **kwargs):
    """Add an argument to the parser for an entry_point function.
    The parameters are the same as for `argparse.ArgumentParser.add_argument`,
    except that the last positional argument is turned into a `help` keyword
    argument.
    Decorators that add positional arguments should appear in the reverse
    order of how they will be input on the command line.
    """
    return functools.partial(_add_param, args, kwargs)


def _parse_disassembly_root(raw):
    name, colon, offset = raw.partition(':')
    offset = int(offset, 0)
    return name, offset


def _folder(filename):
    return os.path.realpath(os.path.join(filename, '..'))


_DSA_ROOT = _folder(_folder(__file__))


_DEFAULT_PATHS = [
    # Default to including all system modules and nothing user-defined.
    'types types',
    '    **',
    'structgroups structgroups',
    '    **'
]

@timed('Loading definition paths...')
def _load_paths(pathfile):
    if pathfile is None:
        return load_lines(PathLoader(_DSA_ROOT, _DSA_ROOT), _DEFAULT_PATHS)
    return load_files(PathLoader(_DSA_ROOT, _folder(pathfile)), pathfile)


@timed('Loading types...')
def _load_types(paths):
    return load_files(TypeLoader(), *paths['types'])


@timed('Loading structgroups...')
def _load_structgroups(types, paths):
    return load_files(StructGroupLoader(types), *paths['structgroups'])


@timed('Loading language...')
def _load_language(pathfile):
    paths = _load_paths(pathfile)
    return _load_structgroups(_load_types(paths), paths)


@timed('Loading binary...')
def _get_data(source):
    with open(source, 'rb') as f:
        return f.read()


# two different diagnostic messages for this,
# so the decoration is invoked dynamically.
def _assemble(infilename, outfilename, language, verbose):
    chunks = load_files(SourceLoader(language), outfilename)
    with open(infilename, 'rb') as f:
        data = bytearray(f.read())
    for position, chunk in chunks.items():
        if verbose:
            trace(f'Test writing {len(chunk)} bytes at 0x{position:X}')
        data[position:position+len(chunk)] = chunk
    return bytes(data)


@timed('Disassembling...')
def _disassemble(language, group_name, position, data, output):
    Disassembler(language, group_name, position, 'main')(data, output)


@timed('Writing to output...')
def _do_output(to_write, binary):
    with open(binary, 'wb') as f:
        f.write(to_write)


@param('source', 'name of file to assemble')
@param('binary', 'source binary file to assemble into')
@param('-o', '--output', 'binary file to write (if not overwriting source)')
@param('-p', '--paths', 'name of input file containing path config info')
@entry_point('Data Structure Assembler - assembly mode')
def dsa(binary, source, paths, output=None):
    data = _get_data(binary)
    language = _load_language(paths)
    action = timed('Assembling...')(_assemble)
    result = action(binary, source, language, False)
    _do_output(result, binary if output is None else output)


@param('output', 'output file name')
@param('root', 'structgroup name and offset for root chunk, e.g. `example:0x123`')
@param('binary', 'source binary file to disassemble from')
@param('-v', '--verify', 'try re-assembling the output and comparing to the source', nargs='?', const=True, default=False)
@param('-p', '--paths', 'name of input file containing path config info')
@entry_point('Data Structure Assembler - disassembly mode')
def dsd(binary, root, output, paths, verify):
    data = _get_data(binary)
    language = _load_language(paths)
    group_name, position = _parse_disassembly_root(root)
    _disassemble(language, group_name, position, data, output)
    if verify:
        action = timed('Reassembling for verification...')(_assemble)
        result = action(binary, output, language, True)
        status = 'OK' if result == data else 'failed'
        trace(f'Verification: {status}.')
