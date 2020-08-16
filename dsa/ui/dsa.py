# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

from ..parsing.file_parsing import load_files
from ..parsing.source_loader import SourceLoader
from .common import get_data, load_language, reporting
from .entrypoint import entry_point, param
from .tracing import timed, trace
from binascii import hexlify
from functools import partial


"""Interface to assembler."""


@timed('Assembling...')
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
        trace(message.format(expanded))
        trace('to accomodate written data.')
    return bytes(data)


def _dumphex(data):
    for i in range(0, len(data), 16):
        hexed = hexlify(data[i:i+16]).upper()
        bytecount = len(hexed) // 2
        result = bytearray(bytecount * 3)
        result[::3] = hexed[::2]
        result[1::3] = hexed[1::2]
        result[2::3] = b' ' * bytecount
        trace(result.decode('ascii'))


@timed('Reassembling for verification...')
def verify_assembly(infilename, outfilename, groups, filters):
    chunks = load_files([outfilename], SourceLoader, groups, filters)
    with open(infilename, 'rb') as f:
        reference = bytearray(f.read())
    offset = 0
    ok, overwrite, fail = 0, 0, 0
    for position, chunk in chunks.items():
        original = reference[position:position+len(chunk)]
        if position < offset:
            trace(f'OVERWRITE at 0x{position:X}: last ended at 0x{offset:X}')
            overwrite += 1
        elif chunk != original:
            trace(f'MISMATCH at 0x{position:X}: ORIGINAL (')
            _dumphex(original)
            trace(f') ASSEMBLED (')
            _dumphex(chunk)
            trace(f')')
            fail += 1
        else:
            ok += 1
        offset = position + len(chunk)
    print()
    total = ok + overwrite + fail
    trace(f'{ok}/{total} OK, {overwrite}/{total} overwrites, {fail}/{total} mismatches')


@timed('Writing to output...')
def _do_output(to_write, binary):
    with open(binary, 'wb') as f:
        f.write(to_write)


@reporting('Running DSA...')
@param('source', 'name of file to assemble')
@param('binary', 'source binary file to assemble into')
@param('-o', '--output', 'binary file to write (if not overwriting source)')
@param('-p', '--paths', 'name of input file containing path config info')
@entry_point('Data Structure Assembler - assembly mode')
def dsa(binary, source, paths, output=None):
    data = get_data(binary)
    groups, filters = load_language(paths)
    result = assemble(binary, source, groups, filters)
    _do_output(result, binary if output is None else output)
