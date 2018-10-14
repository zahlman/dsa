from .assembly import SourceLoader
from .disassembly import Disassembler
from . import errors
from .file_parsing import load_file, load_globs
from .structgroup_loader import StructGroupLoader
from .type_loader import TypeLoader
import argparse
from time import time


class UNRECOGNIZED_PATH_TYPE(errors.MappingError):
    """unrecognized path type `{key}`"""


def _timed(action, *args):
    t = time()
    result = action(*args)
    elapsed = int((time() - t) * 1000)
    print(f'({elapsed} ms)')
    return result


def _load_args(prog, description, *argspecs):
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


def _load_paths(options):
    paths = {
        k: [] if options[k] is None else options[k]
        for k in ('lib_types', 'usr_types', 'lib_structs', 'usr_structs')
    }
    filename = options['paths']
    if filename is not None:
        _populate_paths(paths, filename)
    return paths


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
        {'nargs': '?', 'const': True, 'default': False}
    ]
]


_assembly_args = [
    ['binary', 'source binary file to assemble into', {}],
    ['input', 'name of file to assemble', {}],
    [
        '-o', '--output', 'binary file to write (if not overwriting source)',
        {'nargs': '?'}
    ]
]


_config_paths = [
    ['-p', '--paths', 'name of input file containing path config info', {}],
    [
        '-s', '--lib_structs',
        'path to structgroup definitions (relative to DSA)',
        {'nargs': '*'}
    ],
    [
        '-S', '--usr_structs',
        'path to structgroup definitions (relative to working directory)',
        {'nargs': '*'}
    ],
    [
        '-t', '--lib_types',
        'path to type definitions (relative to DSA)',
        {'nargs': '*'}
    ],
    [
        '-T', '--usr_types',
        'path to type definitions (relative to working directory)',
        {'nargs': '*'}
    ]
]


def _load_language(paths):
    print('Loading types...')
    types = _timed(
        load_globs, TypeLoader(),
        paths['lib_types'], paths['usr_types']
    )
    print('Loading language...')
    return _timed(
        load_globs, StructGroupLoader(types),
        paths['lib_structs'], paths['usr_structs']
    )


def _get_data(source):
    print('Loading binary...')
    with open(source, 'rb') as f:
        return f.read()


def _reassemble(infilename, outfilename, language, verbose):
    chunks = load_file(SourceLoader(language), outfilename)
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


def _dsa(args):
    paths = _load_paths(args)
    data = _timed(_get_data, args['binary'])
    language = _load_language(paths)
    print("Assembling...")
    result = _timed(
        _reassemble, args['binary'], args['input'], language, False
    )
    print("Writing to output...")
    _timed(_do_output, result, args['output'] or args['binary'])


def dsa(binary, source, paths, output=None):
    _dsa({
        'binary': binary, 'input': source, 'paths': paths, 'output': output,
        'lib_types': None, 'lib_structs': None,
        'usr_types': None, 'usr_structs': None
    })


def dsa_cli():
    _dsa(_load_args(
        'dsa',
        'Data Structure Assembler - assembly mode',
        *_assembly_args, *_config_paths
    ))


def _dsd(args):
    paths = _load_paths(args)
    data = _timed(_get_data, args['binary'])
    language = _load_language(paths)
    group_name, position = _parse_entry_point(args['root'])
    print('Setting up...')
    d = _timed(Disassembler, language, group_name, position, 'main')
    print('Disassembling...')
    _timed(d, data, args['output'])
    if args['verify']:
        print('Reassembling for verification...')
        result = _timed(
            _reassemble, args['binary'], args['output'], language, True
        )
        print(f"Verification: {'OK' if result == data else 'failed'}.")


def dsd(binary, root, output, paths, verify):
    _dsd({
        'binary': binary, 'root': root, 'output': output, 'paths': paths,
        'lib_types': None, 'lib_structs': None,
        'usr_types': None, 'usr_structs': None,
        'verify': verify
    })


def dsd_cli():
    _dsd(_load_args(
        'dsd',
        'Data Structure Assembler - disassembly mode',
        *_disassembly_args, *_config_paths
    ))
