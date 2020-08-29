# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

from dsa.errors import UserError
from dsa.parsing.file_parsing import load_files_into
from dsa.parsing.line_parsing import line_parser
from dsa.parsing.token_parsing import make_parser, single_parser
import codecs
from io import BytesIO, StringIO
from pathlib import Path
import re


class BAD_CODEC_LINE(UserError):
    """codec lines must not be indented or marked as meta"""


class BAD_PATTERN(UserError):
    pass


_parse_config = make_parser(
    '`string` interpreter parameters',
    ('string', 'encoding'),
    ('string', 'codec'),
)
_parse_codec_line = line_parser(
    '`string` codec entry',
    single_parser('byte pattern', 'hexdump'),
    single_parser('linewrap', {'true': True, 'false': False}),
    single_parser('label', 'string')
)
_string_line = line_parser(
    '`string` data line', single_parser('name', 'string'), required=1
)


_null_terminated = re.compile(rb'([^\x00]*)\x00?')


_HERE = Path(__file__).absolute().parent


def _read_single(output, data, mapping, size, stream, reader):
    start = stream.tell()
    for amount in range(size, 0, -1):
        data = stream.read(amount)
        try:
            code, newline = mapping[data].parse(stream)
            output.write(code)
            return newline
        except KeyError:
            stream.seek(start)
    # If we run out of options, use the encoding.
    try:
        output.write(reader.read(1))
    except UnicodeDecodeError:
        # Consume one byte to make progress, and try again.
        stream.seek(start)
        fallback = stream.read(1)
        reader.reset()
        output.write(f'[0x{fallback.hex()}]')
    return False


def _decode_gen(data, mapping, encoding):
    stream = BytesIO(data)
    end = len(data)
    max_size = max(len(k) for k in mapping)
    reader = codecs.getreader(encoding)(stream)
    output = StringIO()
    while stream.tell() < end:
        do_newline = _read_single(output, data, mapping, max_size, stream, reader)
        if do_newline:
            yield output.getvalue()
            output.seek(0)
            output.truncate()
    yield output.getvalue()


class Codec:
    _all = {}


    def __init__(self, decode_mapping, encode_mapping):
        self._decode_mapping = decode_mapping
        self._encode_mapping = encode_mapping


    @staticmethod
    def get(name):
        if name not in Codec._all:
            load_files_into(Codec._all, [_HERE / f'{name}.txt'], CodecLoader)
        return Codec._all[name]


    def decode(self, data, encoding):
        return [
            ('', (repr(token),))
            for token in _decode_gen(data, self._decode_mapping, encoding)
        ]


class TextCode:
    def __init__(self, raw, label, linewrap):
        self._raw = raw
        self._template = f'[{label}]'
        self._linewrap = linewrap


    def parse(self, stream):
        # Don't consume any stream data.
        return self._template, self._linewrap


    def format(self, values):
        if len(self._params) != len(values):
            raise ValueError('incorrect number of parameters')
        return self._raw + b''.join(
            p.format(v) for p, v in zip(self._params, values)
        )


class CodecLoader:
    def __init__(self):
        self._decode_mapping = {}
        self._encode_mapping = {}


    def line(self, indent, tokens):
        BAD_CODEC_LINE.require(not indent)
        pattern, newline_count, label = _parse_codec_line(tokens)
        data = BAD_PATTERN.convert(ValueError, bytes, pattern)
        self._decode_mapping[data] = TextCode(data, label, newline_count)


    def result(self):
        return Codec(self._decode_mapping, self._encode_mapping)



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
    match = _null_terminated.match(data)
    text = Codec.get(codec_name).decode(match.group(1), encoding)
    return match.end(), text


def item_size(token):
    # FIXME: We need to know the text to do this properly, but we only
    # get the encoding this way.
    return 0


def assemble(codec_lookup, lines):
    """Produce raw data representing the chunk for the binary.
    The `lines` have already had labels resolved."""
    raise NotImplementedError


alignment = 1
