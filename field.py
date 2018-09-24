from arguments import Arguments, base, boolean, integer, string
from parse_config import parts_of
from functools import partial


class FixedField:
    def __init__(self, name, bits, bias, signed, value, doc):
        self.name = name
        raw = value + bias
        count = 1 << bits
        halfcount = 1 << (bits - 1)
        if signed and raw < 0:
            raw += count
        if not 0 <= raw < count:
            raise ValueError('fixed value out of representable range')
        self.raw = raw
        self.size = bits


    @property
    def is_fixed(self):
        return True


class RawField:
    def __init__(self, name, bits, bias, signed):
        self.name = name
        # The bias is added when assembling, deducted when disassembling.
        self.bits = bits
        self.bias = bias
        self.signed = signed


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
            self.throw(
                f'{value} out of range {self.minimum}..{self.maximum}'
            )
        value += self.bias
        if self.signed and value < 0:
            assert value >= -self.halfcount
            value += self.count
        assert 0 <= value < self.count
        return value


    def __str__(self):
        low, high, base = self.minimum, self.maximum
        return f'Field {self.name} {{range: {low}..{high}}}'


    def throw(self, msg):
        raise ValueError(f'Field {self.name}: {msg}')


class Field:
    def __init__(self, implementation, descriptions, referent, doc):
        # The bias is added when assembling, deducted when disassembling.
        self.implementation = implementation
        self.descriptions = descriptions
        self.referent = referent
        self.doc = doc # Unused for now.


    @property
    def is_fixed(self):
        return False


    @property
    def size(self):
        return self.implementation.bits


    def __str__(self):
        return str(self.implementation)


    def format(self, raw, disassembler, member_name):
        value = self.implementation.value(raw)
        for description in self.descriptions:
            try:
                result = description.format(value)
            except ValueError as e:
                self.implementation.throw(e)
            if result is not None:
                if self.referent is None:
                    return result
                # Otherwise, inform the disassembler about this pointer,
                # and let it provide a label name.
                name = self.implementation.name
                name = member_name if name is None else f'{member_name}_{name}'
                return '@' + disassembler.add(self.referent, value, name)
        # No exceptions, but nothing worked
        self.implementation.throw(f'No valid format for value: {value}')


    def parse(self, text):
        for description in self.descriptions:
            try:
                result = description.parse(text)
            except ValueError as e:
                self.implementation.throw(e)
            if result is not None:
                return self.implementation.raw(result)
        # No exceptions, but nothing worked
        self.implementation.throw(f"Couldn't parse: '{text}'")


def _field(bits, name, fixed, arguments, description_makers, doc, deferred):
    flags = arguments.evaluate(deferred)
    bias, signed, base = flags['bias'], flags['signed'], flags['base']
    if fixed is not None:
        return FixedField(
            name, bits, bias, signed, fixed, doc
        )

    raw = RawField(name, bits, bias, signed)
    return Field(
        raw,
        [
            d(raw.minimum, raw.maximum, bits, base)
            for d in description_makers
        ],
        flags['referent'],
        doc
    )


def field_maker(line_tokens, doc, description_makers, deferral):
    """Creates a factory that will create a Field using deferred info.
    line_tokens -> tokenized line from the config file.
    doc -> associated doc lines.
    description_makers -> factories for contained Descriptions.
    deferral -> accumulator for parameters that will be deferred.

    The factory expects the following parameters:
    deferred -> a dict of deferred parameters used to customize the Field."""
    bnf, *flag_tokens = line_tokens
    bits, name, fixed = parts_of(bnf, ':', 1, 3, False)
    bits = int(bits, 0)
    if fixed is not None:
        fixed = int(fixed, 0)
    arguments = Arguments(
        # TODO: actually process and use 'referent' values.
        {'bias': integer, 'signed': boolean, 'base': base, 'referent': string},
        {'bias': 0, 'signed': False, 'base': hex},
        flag_tokens
    )
    arguments.add_requests(deferral)
    return partial(
        _field, bits, name, fixed, arguments, description_makers, doc
    )
