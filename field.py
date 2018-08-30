from parse_config import parse_base, parse_bool, parse_int
from parse_config import fill_template, parse_flags


class RawField:
    def __init__(self, name, bits, bias, signed, fixed):
        self.name = name
        # The bias is added when assembling, deducted when disassembling.
        self.bits = bits
        self.bias = bias
        self.signed = signed
        self.fixed = fixed


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


    def check_fixed_binary(self, raw):
        value = self.value(raw)
        if self.fixed is not None:
            if value != self.fixed:
                self.throw(
                    f'Expected value {self.fixed} in data; actually {value}'
                )
            return True, None
        return False, value
    
    
    def check_fixed_text(self, text):
        if self.fixed is not None:
            # This value should get hacked in by the parent Option
            assert text is None
            return self.raw(self.fixed) 
        return None


class Field:
    def __init__(self, implementation, descriptions, doc):
        # The bias is added when assembling, deducted when disassembling.
        self.implementation = implementation
        self.descriptions = descriptions
        self.doc = doc # Unused for now.


    @property
    def size(self):
        return self.implementation.bits


    def __str__(self):
        return str(self.implementation)


    def format(self, raw):
        fixed, value = self.implementation.check_fixed_binary(raw)
        if fixed:
            # The parent Option should filter this out
            return value
        for description in self.descriptions:
            try:
                result = description.format(value)
            except ValueError as e:
                self.implementation.throw(e)
            if result is not None:
                return result
        # No exceptions, but nothing worked
        self.implementation.throw(f'No valid format for value: {value}')
    
    
    def parse(self, text):
        result = self.implementation.check_fixed_text(text)
        if result is not None:
            return result
        for description in self.descriptions:
            try:
                result = description.parse(text)
            except ValueError as e:
                self.throw(e)
            if result is not None:
                return self.implementation.raw(result)
        # No exceptions, but nothing worked
        self.implementation.throw(f"Couldn't parse: '{text}'")


def parse_nbo(nbo):
    items = [x.strip() for x in nbo.split(':')]
    if len(items) == 2:
        name, bits = items
        order = None
    elif len(items) == 3:
        name, bits, order = items
        order = int(order, 0)
    else:
        raise ValueError(f'invalid name/bits/order specification')
    return name.strip(), int(bits, 0), order


class FieldBuilder:
    def __init__(self, line_tokens, doc):
        nbo, *flag_tokens = line_tokens
        self.name, self.bits, self.order = parse_nbo(nbo)
        self.flags = parse_flags(
            flag_tokens, 
            {
                'bias': (parse_int, 0),
                'signed': (parse_bool, False),
                'base': (parse_base, hex),
                'fixed': (parse_int, None)
            }
        )
        self.doc = doc
        self.descriptions = []


    def add_description(self, desc):
        self.descriptions.append(desc)


    def create(self, deferred):
        flags = fill_template(self.flags, deferred)
        raw = RawField(
            self.name, self.bits,
            flags['bias'], flags['signed'], flags['fixed'] 
        )
        return self.order, self.bits, flags['fixed'] is not None, Field(
            raw,
            [
                d(raw.minimum, raw.maximum, self.bits, flags['base'])
                for d in self.descriptions
            ],
            self.doc
        )

