from .assembly import SourceLoader
from .disassembly import Disassembler
from . import errors
from .file_parsing import load_files
from .path_loader import PathLoader
from .structgroup_loader import StructGroupLoader
from .type_loader import TypeLoader
import argparse, os
from time import time


class UNRECOGNIZED_PATH_TYPE(errors.MappingError):
    """unrecognized path type `{key}`"""


def _timed(action, *args):
    t = time()
    result = action(*args)
    elapsed = int((time() - t) * 1000)
    print(f'({elapsed} ms)')
    return result


def load_args(prog, description, *argspecs):
    parser = argparse.ArgumentParser(prog=prog, description=description)
    for *names, helptext, kwargs in argspecs:
        parser.add_argument(*names, help=helptext, **kwargs)
    return vars(parser.parse_args())


def _parse_entry_point(raw):
    name, colon, offset = raw.partition(':')
    offset = int(offset, 0)
    return name, offset


def _populate_paths(paths, filename):
    with open(filename) as f:
        for line in f:
            line, mark, comment = line.partition('#')
            line = line.strip()
            if not line:
                continue
            category, path = line.split(None, 1)
            UNRECOGNIZED_PATH_TYPE.get(paths, category).append(path)


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
    return os.path.split(os.path.realpath(filename))[0]


def _load_language(pathfile):
    print('Loading paths...')
    paths = _timed(
        load_files, PathLoader(_folder(__file__), _folder(pathfile)), pathfile
    )
    print('Loading types...')
    types = _timed(load_files, TypeLoader(), *paths['types'])
    print('Loading language...')
    return _timed(load_files, StructGroupLoader(types), *paths['structgroups'])


def _get_data(source):
    print('Loading binary...')
    with open(source, 'rb') as f:
        return f.read()


def _reassemble(infilename, outfilename, language, verbose):
    chunks = load_files(SourceLoader(language), outfilename)
    with open(infilename, 'rb') as f:
        data = bytearray(f.read())
    for position, chunk in chunks.items():
        if verbose:
            print(f'Test writing {len(chunk)} bytes at 0x{position:X}')
        data[position:position+len(chunk)] = chunk
    return bytes(data)


def _do_output(to_write, binary):
    with open(binary, 'wb') as f:
        f.write(to_write)


def dsa(binary, source, pathfile, output=None):
    data = _timed(_get_data, binary)
    language = _load_language(pathfile)
    print("Assembling...")
    result = _timed(
        _reassemble, binary, source, language, False
    )
    print("Writing to output...")
    _timed(_do_output, result, binary if output is None else output)


def dsa_cli():
    dsa(**load_args(
        'dsa',
        'Data Structure Assembler - assembly mode',
        *_assembly_args, *_config_paths
    ))


def dsd(binary, root, output, pathfile, verify):
    data = _timed(_get_data, binary)
    language = _load_language(pathfile)
    group_name, position = _parse_entry_point(root)
    print('Setting up...')
    d = _timed(Disassembler, language, group_name, position, 'main')
    print('Disassembling...')
    _timed(d, data, output)
    if verify:
        print('Reassembling for verification...')
        result = _timed(
            _reassemble, binary, output, language, True
        )
        print('Verification:', 'OK.' if result == data else 'failed.')


def dsd_cli():
    _dsd(load_args(
        'dsd',
        'Data Structure Assembler - disassembly mode',
        *_disassembly_args, *_config_paths
    ))
