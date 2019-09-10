from ..disassembly import Disassembler
from .common import get_data, load_language
from .dsa import reassemble 
from .entrypoint import entry_point, param
from .tracing import timed, trace


"""Interface to disassembler."""


@timed('Disassembling...')
def _disassemble(language, group_name, position, data, output):
    Disassembler(language, group_name, position, 'main')(data, output)


@param('output', 'output file name')
@param('root', 'structgroup name and offset for root chunk, e.g. `example:0x123`')
@param('binary', 'source binary file to disassemble from')
@param('-v', '--verify', 'try re-assembling the output and comparing to the source', action='store_true')
@param('-p', '--paths', 'name of input file containing path config info')
@entry_point('Data Structure Assembler - disassembly mode')
def dsd(binary, root, output, paths, verify=False):
    data = get_data(binary)
    language = load_language(paths)
    group_name, _, position = root.partition(':')
    position = int(position, 0)
    _disassemble(language, group_name, position, data, output)
    if verify:
        result = reassemble(binary, output, language)
        status = 'OK' if result == data else 'failed'
        trace(f'Verification: {status}.')
