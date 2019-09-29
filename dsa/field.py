from .description import Raw
from .errors import MappingError, UserError
from .parsing.line_parsing import arguments, TokenError
from .parsing.token_parsing import base, boolean, integer, string

class UNALIGNED_POINTER(UserError):
    """cannot refer to this address (wrong alignment)"""


class INVALID_LINE(TokenError):
    """not enough tokens for field description line"""


class INVALID_BF(TokenError):
    """invalid bit size and/or fixed value (token should have 1..2 parts, has {actual})"""


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


def field_arguments(tokens):
    return arguments(
        tokens,
        {
            'bias': (integer, 0), 'stride': (integer, 1),
            'signed': (boolean, False), 'base': (base, hex),
            'values': (string, None)
        }
    )


def member_field_data(tokens):
    bf, tokens = INVALID_LINE.shift(tokens)
    bits, fixed = INVALID_BF.pad(bf, 1, 2)
    bits = integer([bits], 'bit count')
    if fixed is None:
        name, tokens = INVALID_LINE.shift(tokens)
        name = string(name, 'field name')
    else:
        name = None
    args = field_arguments(tokens)
    # A later pass will parse the `fixed` spec and create the Field.
    return name, args, fixed, bits
