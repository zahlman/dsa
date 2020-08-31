# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

from dsa.errors import MappingError, UserError
from dsa.parsing.line_parsing import line_parser
from dsa.parsing.token_parsing import make_parser, single_parser
import codecs
from io import BytesIO, StringIO
import re


class UNRECOGNIZED_TAG(MappingError):
    """Unknown tag `{key}`"""


class WRONG_PARAM_COUNT(UserError):
    """`{name}` tag expects `{need}` parameters (got `{got}`)"""


class BAD_ARGUMENT(UserError):
    """Tag argument must be either a positive integer or one of `{param}` (not `{arg}`)"""


_tag_splitter = re.compile(r'(\[.*?\])')


_parse_codec_line = line_parser(
    '`string` codec entry',
    make_parser(
        'line start',
        ('hexdump', 'byte pattern'),
        ({'newline': True, None: False}, 'is EOL?')
    ),
    single_parser('tag label', 'string?'),
    more=True
)
_parse_param = make_parser(
    'tag parameter',
    ('integer', 'number of bytes used'),
    ('[string', 'labels for options')
)


def _read_single(output, data, mapping, sizes, stream, reader):
    start = stream.tell()
    for size in sizes:
        data = stream.read(size)
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


def _decode_gen(data, bound, mapping, encoding):
    stream = BytesIO(data)
    end = len(data)
    reader = codecs.getreader(encoding)(stream)
    output = StringIO()
    sizes = range(max(len(k) for k in mapping), bound, -1)
    while stream.tell() < end:
        do_newline = _read_single(output, data, mapping, sizes, stream, reader)
        if do_newline:
            yield output.getvalue()
            output.seek(0)
            output.truncate()
    yield output.getvalue()


def _process_tag(mapping, tag_name):
    if tag_name.startswith('0x'):
        return UNRECOGNIZED_TAG.convert(
            ValueError, bytes.fromhex, tag_name[2:]
        )
    pieces = tag_name.split()
    for label_count in range(len(pieces), 0, -1):
        try:
            code = mapping[' '.join(pieces[:label_count])]
        except KeyError:
            continue
        else:
            return code.encode_with(pieces[label_count:])
    UNRECOGNIZED_TAG.require(False, key=tag_name)


def _encode_gen(line, mapping, encoding):
    for component in _tag_splitter.split(line):
        if not component.startswith('['):
            yield component.encode(encoding)
            continue
        yield _process_tag(mapping, component[1:-1])


class Codec:
    def __init__(self, allow_zero, decode_mapping, encode_mapping):
        self._bound = -1 if allow_zero else 0
        self._decode_mapping = decode_mapping
        self._encode_mapping = encode_mapping


    def decode(self, data, encoding):
        return [
            ('', (repr(token),))
            for token in _decode_gen(
                data, self._bound, self._decode_mapping, encoding
            )
        ]


    def encode(self, line, encoding):
        return b''.join(_encode_gen(line, self._encode_mapping, encoding))


class TextCode:
    def __init__(self, raw, linewrap, label, params):
        self._raw = raw
        self._sizes, self._options = (), ()
        self._linewrap = linewrap
        self._name = label
        if label is None:
            assert not params
            self._template = f'[0x{raw.hex()}]'
            return
        if params:
            self._sizes, self._options = zip(*(_parse_param(l) for l in params))
        template = ' {}' * len(self._sizes)
        self._template = f'[{label}{template}]'


    def decode_from(self, stream):
        raw = [
            int.from_bytes(stream.read(size), 'little') for size in self._sizes
        ]
        values = [
            option[v] if v < len(option) else str(v)
            for option, v in zip(self._options, raw)
        ]
        # TODO: allow the tag to be parametrized, reading from `stream`.
        return self._template.format(*values), self._linewrap


    def encode_with(self, values):
        assert self._name is not None # should have been handled earlier.
        need, got = len(self._options), len(values)
        WRONG_PARAM_COUNT.require(need==got, name=self._name, need=need, got=got)
        result = bytearray(self._raw)
        for param, arg, size in zip(self._options, values, self._sizes):
            try:
                value = int(arg, 0)
                if value < 0:
                    raise ValueError # require positive value
            except ValueError:
                BAD_ARGUMENT.require(arg in param, arg=arg, param=param)
                value = param.index(arg)
            result.extend(value.to_bytes(size, 'little'))
        return bytes(result)


# The codec loader interface consists of a Loader class. It works like
# the loaders used by the base code, except that there is no `indent` parameter
# to the `line` method (meta lines are handled earlier, and indentation is
# not considered meaningful).
class Loader:
    def __init__(self):
        self._allow_zero = False
        self._decode_mapping = {}
        self._encode_mapping = {}


    def line(self, tokens):
        (raw, linewrap), label, params = _parse_codec_line(tokens)
        code = TextCode(raw, linewrap, label, params)
        if params and not raw:
            # We specified a tag with zero fixed bytes but with params.
            # Therefore, when decoding, we need to look for zero-byte tags.
            self._allow_zero = True
        self._decode_mapping[raw] = code
        self._encode_mapping[label] = code


    def result(self):
        return Codec(self._allow_zero, self._decode_mapping, self._encode_mapping)
