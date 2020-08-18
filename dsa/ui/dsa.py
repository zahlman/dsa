# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

from .common import dsa_entrypoint, get_data, load_language
from .tracing import my_tracer
from ..parsing.file_parsing import load_files
from ..parsing.source_loader import SourceLoader
from binascii import hexlify


"""Interface to assembler."""


def assemble(infilename, outfilename, groups, filters):
    chunks = load_files([outfilename], SourceLoader, groups, filters)
    with open(infilename, 'rb') as f:
        data = bytearray(f.read())
    last, expanded = 0, 0
    for position, chunk in chunks.items():
        assert position >= last
        last = position + len(chunk)
        needed = last - len(data)
        if needed > 0:
            expanded += needed
            data.extend(bytes(needed))
        data[position:position+len(chunk)] = chunk
    if expanded:
        message = 'Warning: output binary was expanded by {0} (0x{0:X}) bytes'
        my_tracer.trace(message.format(expanded))
        my_tracer.trace('to accomodate written data.')
    return bytes(data)


def _dumphex(data):
    for i in range(0, len(data), 16):
        hexed = hexlify(data[i:i+16]).upper()
        bytecount = len(hexed) // 2
        result = bytearray(bytecount * 3)
        result[::3] = hexed[::2]
        result[1::3] = hexed[1::2]
        result[2::3] = b' ' * bytecount
        my_tracer.trace(result.decode('ascii'))


def verify_assembly(infilename, outfilename, groups, filters):
    chunks = load_files([outfilename], SourceLoader, groups, filters)
    with open(infilename, 'rb') as f:
        reference = bytearray(f.read())
    offset = 0
    ok, overwrite, fail = 0, 0, 0
    for position, chunk in chunks.items():
        original = reference[position:position+len(chunk)]
        if position < offset:
            my_tracer.trace(
                f'OVERWRITE at 0x{position:X}: last ended at 0x{offset:X}'
            )
            overwrite += 1
        elif chunk != original:
            my_tracer.trace(f'MISMATCH at 0x{position:X}: ORIGINAL (')
            _dumphex(original)
            my_tracer.trace(f') ASSEMBLED (')
            _dumphex(chunk)
            my_tracer.trace(f')')
            fail += 1
        else:
            ok += 1
        offset = position + len(chunk)
    print()
    total = ok + overwrite + fail
    my_tracer.trace(', '.join((
        f'{ok}/{total} OK',
        f'{overwrite}/{total} overwrites',
        f'{fail}/{total} mismatches'
    )))


@dsa_entrypoint(
    description='Data Structure Assembler - assembly mode',
    message='Running DSA...',
    source='name of file to assemble',
    binary='source binary file to assemble into',
    _output='binary file to write (if not overwriting source)',
    _paths='name of input file containing path config info'
)
def dsa(binary, source, paths, output=None):
    data = get_data(binary)
    groups, filters = load_language(paths)
    with my_tracer('Assembling'):
        result = assemble(binary, source, groups, filters)
    with my_tracer('Writing to output'):
        with open(binary if output is None else output, 'wb') as f:
            f.write(result)
