# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

from dsa.errors import MappingError
from dsa.parsing.line_parsing import line_parser
from dsa.parsing.token_parsing import make_parser, single_parser
import codecs
import re


class NO_SUCH_CODEC(MappingError):
    """no string codec named `{key}`"""


_parse_config = make_parser(
    '`string` interpreter parameters',
    ('string', 'encoding'),
    ('string', 'codec'),
)
_string_line = line_parser(
    '`string` data line', single_parser('content', 'string'), required=1
)


_null_terminated = re.compile(rb'([^\x00]*)\x00?')


def disassemble(codec_lookup, config, chunk_label, data, register, label_ref):
    """Produce formatted file contents for the chunk.
    In this case, we produce a line with a filename, and write the file;
    we ignore the `register` and `label_ref` callbacks completely since the
    file contents will not be examined for pointers or labels.
    `codec_lookup` -> library of codecs that might be useful here.
    `config` -> additional parameters specified by the Pointer to the chunk.
    `chunk_label` -> label that will be applied to the chunk.
    `data` -> underlying chunk data.
    `register` -> callback to request disassembling another chunk.
    `label_ref` -> callback to retrieve label text for a pointer."""
    encoding, codec_name = _parse_config(config)
    codec = NO_SUCH_CODEC.get(codec_lookup, codec_name)
    match = _null_terminated.match(data)
    text = codec.decode(match.group(1), encoding)
    return match.end(), text


def item_size(token):
    # FIXME: We need to know the text to do this properly, but we only
    # get the encoding this way.
    return 0


def assemble(codec_lookup, config, lines):
    """Produce raw data representing the chunk for the binary.
    The `lines` have already had labels resolved."""
    encoding, codec_name = _parse_config(config)
    codec = NO_SUCH_CODEC.get(codec_lookup, codec_name)
    return b''.join(
        codec.encode(_string_line(line)[0], encoding)
        for line in lines
    )


alignment = 1
