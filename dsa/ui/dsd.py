# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

from ..disassembly import Disassembler
from .common import dsa_entrypoint, get_data, load_language
from .dsa import verify_assembly
from .tracing import timed, trace


"""Interface to disassembler."""


@timed('Disassembling...')
def _disassemble(groups, group_name, filters, position, data, output):
    Disassembler(data, groups, filters, group_name, position)(output)


@dsa_entrypoint(
    description='Data Structure Assembler - disassembly mode',
    message='Running DSD...',
    output='output file name',
    root='structgroup name and offset for root chunk, e.g. `example:0x123`',
    binary='source binary file to disassemble from',
    _verify={
        'help': 'try re-assembling the output and comparing to the source',
        'action': 'store_true'
    },
    _paths='name of input file containing path config info'
)
def dsd(binary, root, output, paths, verify=False):
    data = get_data(binary)
    groups, filters = load_language(paths)
    group_name, _, position = root.partition(':')
    position = int(position, 0)
    _disassemble(groups, group_name, filters, position, data, output)
    if verify:
        verify_assembly(binary, output, groups, filters)
