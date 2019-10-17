from ..disassembly import Disassembler
from .common import get_data, load_language, reporting
from .dsa import verify_assembly
from .entrypoint import entry_point, param
from .tracing import timed, trace


"""Interface to disassembler."""


@timed('Disassembling...')
def _disassemble(groups, group_name, filters, position, data, output):
    Disassembler(data, groups, filters, group_name, position)(output)


@reporting('Running DSD...')
@param('output', 'output file name')
@param(
    'root', 'structgroup name and offset for root chunk, e.g. `example:0x123`'
)
@param('binary', 'source binary file to disassemble from')
@param(
    '-v', '--verify',
    'try re-assembling the output and comparing to the source',
    action='store_true'
)
@param('-p', '--paths', 'name of input file containing path config info')
@entry_point('Data Structure Assembler - disassembly mode')
def dsd(binary, root, output, paths, verify=False):
    data = get_data(binary)
    groups, filters = load_language(paths)
    group_name, _, position = root.partition(':')
    position = int(position, 0)
    _disassemble(groups, group_name, filters, position, data, output)
    if verify:
        verify_assembly(binary, output, groups, filters)
