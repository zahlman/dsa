# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

from .common import dsa_entrypoint, get_data
from .tracing import my_tracer
from ..language import Language


"""Interface to assembler."""


def apply(chunks, data):
    data = bytearray(data)
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


@dsa_entrypoint(
    description='Data Structure Assembler - assembly mode',
    message='Running DSA...',
    binary='source binary file to assemble into',
    source='name of file to assemble',
    _output='binary file to write (if not overwriting source)',
    _libraries={'help': 'symbolic names of libraries to use', 'nargs': '*'},
    _paths={'help': 'paths to roots of libraries to use', 'nargs': '*'},
    _target='target language to build from libraries'
)
def dsa(binary, source, output=None, libraries=(), paths=(), target=None):
    data = get_data(binary)
    my_language = Language.create(libraries, paths, target)
    with my_tracer('Assembling'):
        result = apply(my_language.assemble(source), data)
    with my_tracer('Writing to output'):
        with open(binary if output is None else output, 'wb') as f:
            f.write(result)
