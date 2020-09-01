# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

from .common import dsa_entrypoint, get_data
from .tracing import my_tracer
from ..language import Language


"""Interface to disassembler."""


def _dumphex(data):
    for i in range(0, len(data), 16):
        my_tracer.trace(data[i:i+16].hex(' '))


def verify_assembly(chunks, data):
    offset = 0
    ok, overwrite, fail = 0, 0, 0
    for position, chunk in chunks.items():
        original = data[position:position+len(chunk)]
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
    my_tracer.trace('')
    total = ok + overwrite + fail
    my_tracer.trace(', '.join((
        f'{ok}/{total} OK',
        f'{overwrite}/{total} overwrites',
        f'{fail}/{total} mismatches'
    )))


def root_data(text):
    location, name, *params = text.split(':')
    return (name, params, int(location, 0))


@dsa_entrypoint(
    description='Data Structure Assembler - disassembly mode',
    message='Running DSD',
    binary='source binary file to disassemble from',
    root='offset and interpreter name/params for root chunk, e.g. `0x123:example:param`',
    output='output file name',
    _verify={
        'help': 'try re-assembling the output and comparing to the source',
        'action': 'store_true'
    },
    _paths='name of input file containing path config info'
)
def dsd(binary, root:root_data, output, paths, verify=False):
    data = get_data(binary)
    my_language = Language.load(paths)
    with my_tracer('Disassembling'):
        my_language.disassemble(data, root, output)
    if verify:
        with my_tracer('Reassembling for verification'):
            verify_assembly(my_language.assemble(output), data)
