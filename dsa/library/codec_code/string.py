# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

from dsa.errors import MappingError, UserError
from dsa.parsing.line_parsing import line_parser
from dsa.parsing.token_parsing import single_parser
import codecs
from io import BytesIO, StringIO
import re


class UNRECOGNIZED_TAG(MappingError):
    """Unknown tag `{key}`"""


class BAD_LABEL_NAME(UserError):
    """Explicitly provided label name may not start with `0x`"""


_tag_splitter = re.compile(r'(\[.*?\])')


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
            code, newline = mapping[data].decode_from(stream)
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


def _encode_gen(line, mapping, encoding):
    for component in _tag_splitter.split(line):
        if not component.startswith('['):
            yield component.encode(encoding)
            continue
        tag_name = component[1:-1]
        if tag_name.startswith('0x'):
            yield UNRECOGNIZED_TAG.convert(
                ValueError, bytes.fromhex, tag_name[2:]
            )
        else:
            yield UNRECOGNIZED_TAG.get(mapping, component[1:-1]).encode_with(())


class Codec:
    def __init__(self, decode_mapping, encode_mapping):
        self._decode_mapping = decode_mapping
        self._encode_mapping = encode_mapping


    def decode(self, data, encoding):
        return [
            ('', (repr(token),))
            for token in _decode_gen(data, self._decode_mapping, encoding)
        ]


    def encode(self, line, encoding):
        return b''.join(_encode_gen(line, self._encode_mapping, encoding))


class TextCode:
    def __init__(self, raw, linewrap, label):
        self._raw = raw
        BAD_LABEL_NAME.require(not label.startswith('0x'))
        self._template = f'[{label}]'
        self._linewrap = linewrap
        self._params = () # stub


    def decode_from(self, stream):
        # TODO: allow the tag to be parametrized, reading from `stream`.
        return self._template, self._linewrap


    def encode_with(self, values):
        # TODO: allow the tag to be parametrized, encoding the `values`.
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
