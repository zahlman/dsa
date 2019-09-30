from .description import Raw
from .errors import MappingError, UserError
from .parsing.line_parsing import argument_parser, TokenError
from .parsing.token_parsing import make_parser

class UNALIGNED_POINTER(UserError):
    """cannot refer to this address (wrong alignment)"""


class INVALID_LINE(TokenError):
    """not enough tokens for field description line"""


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


class Field:
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


def make_field(bits, args, description_lookup):
    return Field(
        FieldTranslation(bits, args.bias, args.stride, args.signed),
        args.base,
        Raw if args.values is None else MISSING_DESCRIPTION.get(
            description_lookup, args.values
        )
    )


field_arguments = argument_parser(
    {'bias': 0, 'stride': 1, 'signed': False, 'base': hex, 'values': None},
    bias='integer', stride='positive', values='string',
    signed={None: True, 'true': True, 'false': False},
    base={'2': bin, '8': oct, '10': str, '16': hex}
)


_field_size_parser = make_parser(
    'field size/value info',
    ('positive', 'field size'),
    ('string?', 'fixed value') # will be parsed later,
    # once a type has been loaded from this line, according to that type.
)


_field_name_parser = make_parser(
    'field name',
    ('string', 'name')
)


def member_field_data(tokens):
    bf, tokens = INVALID_LINE.shift(tokens)
    bits, fixed = _field_size_parser(bf)
    if fixed is None:
        name, tokens = INVALID_LINE.shift(tokens)
        name = _field_name_parser(name)[0]
    else:
        name = None
    args = field_arguments(tokens)
    # A later pass will parse the `fixed` spec and create the Field.
    return name, args, fixed, bits
