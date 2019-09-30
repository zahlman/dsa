from .description import Raw
from .errors import MappingError, UserError
from .parsing.line_parsing import argument_parser, line_parser
from .parsing.token_parsing import make_parser, single_parser


class UNALIGNED_POINTER(UserError):
    """cannot refer to this address (wrong alignment)"""


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
    args = field_arguments(tokens)
    # A later pass will parse the `fixed` spec and create the Field.
    return name, args, fixed, bits
