# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

from dsa.parsing.line_parsing import line_parser
from dsa.parsing.token_parsing import single_parser
import codecs
from io import BytesIO, StringIO


_parse_codec_line = line_parser(
    '`string` codec entry',
    single_parser('byte pattern', 'hexdump'),
    single_parser('linewrap', {'true': True, 'false': False}),
    single_parser('label', 'string')
)


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
    size = max(len(k) for k in mapping)
    reader = codecs.getreader(encoding)(stream)
    output = StringIO()
    while stream.tell() < end:
        do_newline = _read_single(output, data, mapping, size, stream, reader)
        if do_newline:
            yield output.getvalue()
            output.seek(0)
            output.truncate()
    yield output.getvalue()


class Codec:
    def __init__(self, decode_mapping, encode_mapping):
        self._decode_mapping = decode_mapping
        self._encode_mapping = encode_mapping


    def decode(self, data, encoding):
        return [
            ('', (repr(token),))
            for token in _decode_gen(data, self._decode_mapping, encoding)
        ]


class TextCode:
    def __init__(self, raw, linewrap, label):
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


# The codec loader interface consists of a Loader class. It works like
# the loaders used by the base code, except that there is no `indent` parameter
# to the `line` method (meta lines are handled earlier, and indentation is
# not considered meaningful).
class Loader:
    def __init__(self):
        self._decode_mapping = {}
        self._encode_mapping = {}


    def line(self, tokens):
        raw, linewrap, label = _parse_codec_line(tokens)
        code = TextCode(raw, linewrap, label)
        self._decode_mapping[raw] = code
        self._encode_mapping[label] = code


    def result(self):
        return Codec(self._decode_mapping, self._encode_mapping)
