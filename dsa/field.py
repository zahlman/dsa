from .description import Raw
from .errors import MappingError, UserError
from .parsing.line_parsing import argument_parser, line_parser
from .parsing.token_parsing import make_parser, single_parser


class UNALIGNED_POINTER(UserError):
    """cannot refer to this address (wrong alignment)"""


class TEXT_BYTES(UserError):
    """Text field size in bits must be a multiple of 8"""


class ENCODING_NOT_SOLO(UserError):
    """`encoding` flag may only appear by itself"""


class TOO_MUCH_TEXT(UserError):
    """encoded text won't fit in field of {size} bytes"""


class MISSING_DESCRIPTION(MappingError):
    """unrecognized description name `{key}`"""


class FieldTranslation:
    def __init__(self, bits, bias, stride, signed):
        self.bits = bits
        self.bias = bias
        self.stride = stride
        self.signed = signed


    @property
    def size(self):
        return self.bits


    @property
    def count(self):
        return 1 << self.bits


    @property
    def halfcount(self):
        return 1 << (self.bits - 1)


    # Convert unsigned value from the data into one that will be formatted.
    def value(self, raw):
        assert 0 <= raw < self.count
        if self.signed and raw >= self.halfcount:
            raw -= self.count
        return (raw * self.stride) + self.bias


    # Convert value computed from parsing into one stored in the data.
    def raw(self, value):
        # Should be guaranteed by the underlying Description(s).
        value, remainder = divmod(value - self.bias, self.stride)
        UNALIGNED_POINTER.require(not remainder)
        if self.signed and value < 0:
            assert value >= -self.halfcount
            value += self.count
        assert 0 <= value < self.count
        return value


class NumericField:
    def __init__(self, translation, formatter, description):
        self.translation = translation
        self.formatter = formatter
        self.description = description


    @property
    def size(self):
        return self.translation.size


    def bias(self, raw):
        return self.translation.value(raw)


    def pointer_value(self, raw):
        value = self.translation.value(raw)
        return self.description.pointer_value(value)


    def format(self, raw):
        value = self.translation.value(raw)
        return self.description.format(value, self.formatter)


    def parse(self, text):
        result = self.description.parse(text)
        if result is not None:
            result = self.translation.raw(result)
        return result


class TextField:
    def __init__(self, encoding, bits):
        self._encoding = encoding
        TEXT_BYTES.require(bits % 8 == 0)
        self._bits = bits


    @property
    def size(self):
        return self._bits


    def bias(self, raw):
        raise NotImplementedError # FIXME


    def pointer_value(self, raw):
        return None


    def format(self, raw):
        # TODO: make stripping optional when disassembling.
        text = raw.to_bytes(self._bits // 8, 'little').rstrip(b'\x00')
        result = self._encoding.decode(text)[0]
        return result


    def parse(self, text):
        value = int.from_bytes(self._encoding.encode(text)[0], 'little')
        TOO_MUCH_TEXT.require(value < (1 << self._bits), size=(self._bits // 8))
        return value


_field_argument_parser = argument_parser(
    bias='integer', stride='positive', values='string',
    encoding='encoding',
    signed={None: True, 'true': True, 'false': False},
    base={'2': bin, '8': oct, '10': str, '16': hex}
)


# also used by Member.
def numeric_field_maker(data, bits):
    get = data.get
    translation = FieldTranslation(
        bits, get('bias', 0), get('stride', 1), get('signed', False)
    )
    formatter = get('base', hex)
    values = get('values', None)
    return lambda lookup: NumericField(
        translation, formatter,
        Raw if values is None else MISSING_DESCRIPTION.get(lookup, values)
    )


def _field_maker(data, bits):
    if 'encoding' in data:
        ENCODING_NOT_SOLO.require(len(data) == 1)
        # ignore the lookup, but still defer creation.
        return lambda lookup: TextField(data['encoding'], bits)
    return numeric_field_maker(data, bits)


_field_size_parser = line_parser(
    'component of non-pointer member',
    make_parser(
        'size/value info',
        ('positive', 'field size'),
        ('string?', 'fixed value') # will be parsed later,
        # once a type has been loaded from this line, according to that type.
    ),
    required=1, more=True
)


_field_name_parser = line_parser(
    'component of non-pointer member',
    single_parser('name', 'string'),
    extracted=1, required=1, more=True
)


def member_field_data(tokens):
    (bits, fixed), tokens = _field_size_parser(tokens)
    if fixed is None:
        name, tokens = _field_name_parser(tokens)
    else:
        name = None
    make_field = _field_maker(_field_argument_parser(tokens), bits)
    # A later pass will parse the `fixed` spec and create the Field.
    # But this can't happen until after the first pass, because the
    # description lookup needs to be built first.
    # We also need to report the `bits` size so the Member can assemble
    # a mask for all the fixed values.
    return name, make_field, fixed, bits
