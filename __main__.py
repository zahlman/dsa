from .file_parsing import load_globs
from . import main
from .structgroup_loader import StructGroupDescriptionLSM
from .type_loader import TypeDescriptionLSM
import argparse
from time import time


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
            main.UNRECOGNIZED_PATH_TYPE.get(paths, category).append(path)


def _load_paths(options):
    paths = {
        k: [] if options[k] is None else options[k]
        for k in ('lib_types', 'usr_types', 'lib_structs', 'usr_structs')
    }
    filename = options['paths']
    if filename is not None:
        _populate_paths(paths, filename)
    return paths


_base_args = [
    ['binary', 'binary source file to disassemble from', {}],
    ['output', 'output file name', {}]
]


_disassembly_root = [
    [
        'root',
        'structgroup name and offset for root chunk, e.g. `example:0x123`',
        {}
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
        load_globs, TypeDescriptionLSM(),
        paths['lib_types'], paths['usr_types']
    )
    print('Loading language...')
    return _timed(
        load_globs, StructGroupDescriptionLSM(types),
        paths['lib_structs'], paths['usr_structs']
    )


def _get_data(source):
    print('Loading binary...')
    with open(source, 'rb') as f:
        return f.read()


def dsa():
    args = _load_args(
        'dsa',
        'Data Structure Assembler - disassembly mode',
        *_base_args, *_disassembly_root, *_config_paths
    )
    paths = _load_paths(args)
    group_name, position = _parse_entry_point(args['root'])
    data = _timed(_get_data, args['binary'])
    language = _load_language(paths)
    print('Setting up...')
    d = _timed(main.Disassembler, language, group_name, position, 'main')
    print('Disassembling...')
    _timed(d, data, args['output'])


if __name__ == '__main__':
    dsa()
