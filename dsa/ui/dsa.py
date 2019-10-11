from ..parsing.file_parsing import load_files
from ..parsing.source_loader import SourceLoader
from .common import get_data, load_language
from .entrypoint import entry_point, param
from .tracing import timed, trace
from functools import partial


"""Interface to assembler."""


@timed('Assembling...')
def assemble(infilename, outfilename, groups, filters):
    chunks = load_files([outfilename], SourceLoader, groups, filters)
    with open(infilename, 'rb') as f:
        data = bytearray(f.read())
    for position, chunk in chunks.items():
        data[position:position+len(chunk)] = chunk
    return bytes(data)


@timed('Reassembling for verification...')
def verify_assembly(infilename, outfilename, groups, filters):
    chunks = load_files([outfilename], SourceLoader, groups, filters)
    with open(infilename, 'rb') as f:
        reference = bytearray(f.read())
    offset = 0
    ok, overwrite, fail = 0, 0, 0
    for position, chunk in chunks.items():
        if position < offset:
            print('O', end='') # overwrote previous chunk
            overwrite += 1
        elif reference[position:position+len(chunk)] != chunk:
            print('X', end='') # doesn't match existing data
            fail += 1
        else:
            print('.', end='')
            ok += 1
        offset = position + len(chunk)
    print()
    total = ok + overwrite + fail
    trace(f'{ok}/{total} OK, {overwrite}/{total} overwrites, {fail}/{total} mismatches')


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
    data = get_data(binary)
    groups, filters = load_language(paths)
    result = assemble(binary, source, groups, filters)
    _do_output(result, binary if output is None else output)
