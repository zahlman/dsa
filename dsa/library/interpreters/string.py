from dsa.parsing.line_parsing import line_parser
from dsa.parsing.token_parsing import make_parser, single_parser
import os, re


_parse_config = make_parser(
    '`string` interpreter parameters',
    ('string', 'encoding'),
    ('integer?', 'count'),
)
_text_token = single_parser('name', 'string')
_string_line = line_parser(
    # Two strings per line: the encoding and the actual text.
    '`string` data line', _text_token, _text_token, required=2
)


_null_terminated = re.compile(rb'([^\x00]*)\x00?')


def _get_strings(data, encoding, count):
    position = 0
    for i in range(count):
        match = _null_terminated.match(data, position)
        yield ('', (encoding,), (repr(match.group(1).decode(encoding)),))
        position = match.end()
    yield position


def disassemble(config, chunk_label, data, register, label_ref):
    """Produce formatted file contents for the chunk.
    In this case, we produce a line with a filename, and write the file;
    we ignore the `register` and `label_ref` callbacks completely since the
    file contents will not be examined for pointers or labels.
    `config` -> additional parameters specified by the Pointer to the chunk.
    `chunk_label` -> label that will be applied to the chunk.
    `data` -> underlying chunk data.
    `register` -> callback to request disassembling another chunk.
    `label_ref` -> callback to retrieve label text for a pointer."""
    encoding, count = _parse_config(config)
    if count is None:
        count = 1
    raw = tuple(_get_strings(data, encoding, count))
    return raw[-1], raw[:-1]


def item_size(token):
    # FIXME: We need to know the text to do this properly, but we only
    # get the encoding this way.
    return 0


def assemble(lines):
    """Produce raw data representing the chunk for the binary.
    The `lines` have already had labels resolved.
    When assembling, we allow multiple file names - one per line -
    and concatenate the file contents."""
    result = bytearray()
    for line in lines:
        encoding, text = _string_line(line)
        result.extend(text.encode(encoding))
    return bytes(result)
