from ..assembly import SourceLoader
from ..disassembly import Disassembler
from ..file_parsing import load_files
from ..path_loader import PathLoader
from ..structgroup_loader import StructGroupLoader
from ..type_loader import TypeLoader
from .diagnostic import timed, trace
import argparse, os


def load_args(prog, description, *argspecs):
    parser = argparse.ArgumentParser(prog=prog, description=description)
    for *names, helptext, kwargs in argspecs:
        parser.add_argument(*names, help=helptext, **kwargs)
    return vars(parser.parse_args())


def _parse_entry_point(raw):
    name, colon, offset = raw.partition(':')
    offset = int(offset, 0)
    return name, offset


_disassembly_args = [
    ['binary', 'source binary file to disassemble from', {}],
    ['output', 'output file name', {}],
    [
        'root',
        'structgroup name and offset for root chunk, e.g. `example:0x123`',
        {}
    ],
    [
        '-v', '--verify',
        'try re-assembling the output and comparing to the source',
        {'const': True, 'default': False}
    ]
]


_assembly_args = [
    ['binary', 'source binary file to assemble into', {}],
    ['input', 'name of file to assemble', {}],
    [
        '-o', '--output', 'binary file to write (if not overwriting source)', {}
    ]
]


_config_paths = [
    ['-p', '--paths', 'name of input file containing path config info', {}],
]


def _folder(filename):
    return os.path.realpath(os.path.join(filename, '..'))


_DSA_ROOT = _folder(_folder(__file__))


@timed('Loading definition paths...')
def _load_paths(pathfile):
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


def dsa(binary, source, pathfile, output=None):
    data = _get_data(binary)
    language = _load_language(pathfile)
    action = timed('Assembling...')(_assemble)
    result = action(binary, source, language, False)
    _do_output(result, binary if output is None else output)


def dsa_cli():
    dsa(**load_args(
        'dsa',
        'Data Structure Assembler - assembly mode',
        *_assembly_args, *_config_paths
    ))


def dsd(binary, root, output, pathfile, verify):
    data = _get_data(binary)
    language = _load_language(pathfile)
    group_name, position = _parse_entry_point(root)
    _disassemble(language, group_name, position, data, output)
    if verify:
        action = timed('Reassembling for verification...')(_assemble)
        result = action(binary, output, language, True)
        status = 'OK' if result == data else 'failed'
        trace(f'Verification: {status}.')


def dsd_cli():
    dsd(**load_args(
        'dsd',
        'Data Structure Assembler - disassembly mode',
        *_disassembly_args, *_config_paths
    ))
