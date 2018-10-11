from description import Raw
import errors
from line_parsing import arguments, base, boolean, integer, string, TokenError
from functools import partial


class INVALID_BNF(TokenError):
    """invalid bits/name/fixed data (token should have 1..3 parts, has {actual})"""


class MISSING_DESCRIPTION(errors.MappingError):
    """unrecognized description name `{key}`"""


class FIXED_REFERENT(errors.UserError):
    """fixed field may not have a referent"""


class FieldTranslation:
    def __init__(self, bits, bias, signed):
        self.bits = bits
        self.bias = bias
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


    @property
    def minimum(self):
        return (-self.halfcount if self.signed else 0) - self.bias


    @property
    def maximum(self):
        return (self.halfcount if self.signed else self.count) - 1 - self.bias


    # Convert unsigned value from the data into one that will be formatted.
    def value(self, raw):
        assert 0 <= raw < self.count
        if self.signed and raw >= self.halfcount:
            raw -= self.count
        return raw - self.bias


    # Convert value computed from parsing into one stored in the data.
    def raw(self, value):
        # Should be guaranteed by the underlying Description(s).
        assert self.minimum <= value <= self.maximum
        value += self.bias
        if self.signed and value < 0:
            assert value >= -self.halfcount
            value += self.count
        assert 0 <= value < self.count
        return value


class Field:
    def __init__(
        self, translation, formatter, description, referent
    ):
        self.translation = translation
        self.formatter = formatter
        self.description = description
        self.referent = referent


    @property
    def size(self):
        return self.translation.size


    # When formatting, exceptions are not raised at this level, since some
    # source data might only be formattable by certain Options. Instead, we
    # return `None` and let the Member iterate to an Option that works.
    def format(self, raw, disassembler, name):
        value = self.translation.value(raw)
        result = self.description.format(value, self.formatter)
        if result is None or self.referent is None:
            return result
        # If we have a valid pointer, inform the disassembler about it,
        # and get a label name from there.
        return '@' + disassembler.add(self.referent, value, name)


    def parse(self, text):
        result = self.description.parse(text)
        if result is not None:
            result = self.translation.raw(result)
        return result


def make_field(line_tokens, description_lookup):
    bnf, *flag_tokens = line_tokens
    bits, name, fixed = INVALID_BNF.pad(bnf, 1, 3)
    bits = errors.parse_int(bits, 'bit count')
    args = arguments(
        flag_tokens,
        {
            # TODO: use `stride`.
            'bias': (integer, 0), 'stride': (integer, 1),
            'signed': (boolean, False), 'base': (base, hex),
            'values': (string, None), 'referent': (string, None)
        }
    )
    field = Field(
        translation=FieldTranslation(bits, args.bias, args.signed),
        formatter=args.base,
        description=Raw if args.values is None else MISSING_DESCRIPTION.get(
            description_lookup, args.values
        ),
        referent=args.referent
    )
    if fixed is not None:
        FIXED_REFERENT.require(args.referent is None)
        fixed = field.parse(fixed)
    return name, field, fixed, bits
