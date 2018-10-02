from arguments import base, boolean, integer, parameters, string
from description import Raw
from parse_config import parts_of
from functools import partial


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
        if not self.minimum <= value <= self.maximum:
            raise ValueError(
                f'{value} out of range {self.minimum}..{self.maximum}'
            )
        value += self.bias
        if self.signed and value < 0:
            assert value >= -self.halfcount
            value += self.count
        assert 0 <= value < self.count
        return value


class Field:
    def __init__(
        self, name, translation, formatter, description, referent, doc
    ):
        self.name = name
        self.translation = translation
        self.formatter = formatter
        self.description = description
        self.referent = referent
        self.doc = doc


    @property
    def size(self):
        return self.translation.size


    def throw(self, msg):
        raise ValueError(f'Field {self.name}: {msg}')


    # When formatting, exceptions are not raised at this level, since some
    # source data might only be formattable by certain Options. Instead, we
    # return `None` and let the Member iterate to an Option that works.
    def format(self, raw, disassembler, member_name):
        value = self.translation.value(raw)
        result = self.description.format(value, self.formatter)
        if result is None or self.referent is None:
            return result
        # If we have a valid pointer, inform the disassembler about it,
        # and get a label name from there.
        name = self.name
        name = member_name if name is None else f'{member_name}_{name}'
        return '@' + disassembler.add(self.referent, value, name)


    def parse(self, text):
        # TODO: handle referent labels.
        try:
            result = self.description.parse(text)
            if result is not None:
                result = self.translation.raw(result)
            return result
        except ValueError as e:
            self.throw(e)


def make_field(line_tokens, doc, description_lookup):
    """Creates a factory that will create a Field later, along with the
    `fixed` value (or None) that it will parse later, and the field size.
    line_tokens -> tokenized line from the config file.
    doc -> associated doc lines.

    The factory expects the following parameters:
    description -> resolved Description object for the field."""
    bnf, *flag_tokens = line_tokens
    bits, name, fixed = parts_of(bnf, ':', 1, 3, False)
    bits = int(bits, 0)
    params = parameters(
        {
            'bias': integer, 'signed': boolean, 'base': base,
            'referent': string, 'values': string
        },
        flag_tokens
    )
    translation = FieldTranslation(
        bits, params.get('bias', 0), params.get('signed', False)
    )
    try:
        values = params['values']
        try:
            description = description_lookup[values]
        except KeyError:
            raise ValueError(f"unrecognized description name '{values}'")
    except KeyError:
        description = Raw
    referent = params.get('referent', None)
    field = Field(
        name, translation, params.get('base', hex),
        description, referent, doc
    )
    if fixed is not None:
        if referent is not None:
            raise ValueError('fixed field may not have a referent')
        fixed = field.parse(fixed)
    return field, fixed, bits
