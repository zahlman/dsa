# A Type represents the semantics of a small chunk of data - more or less
# atomic, typically no more than 4 bytes. It logically consists of one or more
# Options for representing the data, each being a way to format the data into
# a readable text string and parse the text back into data. Each Option is
# logically a sequence of Fields, representing sub-ranges of the bits in the
# data chunk. Each Field can either be represented according to one or more
# Descriptions of the underlying field value, or else has a fixed value.
# The Options for a given Type shall each have a different number of Fields in
# them, all represent the same number of bits of data, and have at least one
# Field each. The data thus described shall be a whole number of bytes
# (non-zero multiple of 8 bits), completely described by each Option.


class LabelledRangeDescription:
    def __init__(self, lowest, highest, label, numeric_formatter):
        self.lowest = lowest
        self.highest = highest
        self.label = label
        self.numeric_formatter = numeric_formatter
        # When parsing, any base is allowed with the appropriate prefix.


    def __str__(self):
        label = self.label
        low = self.numeric_formatter(self.lowest)
        high = self.numeric_formatter(self.highest)
        size = self.highest - self.lowest
        name = 'LabelledRangeDescription'
        if size:
            return f'{name}: {label}(0)={low} .. {label}({size})={high}'
        return f'{name}: {label}={low}'


    def format(self, value):
        if value < self.lowest or value > self.highest:
            # Might still be representable another way.
            return None
        text = self.numeric_formatter(value)
        # Special case: when the range describes a single number, the label
        # is not annotated with an offset.
        if self.lowest == self.highest:
            return self.label
        # Otherwise, it's annotated thus:
        offset = value - self.lowest
        return f'{self.label}({text})'


    def parse(self, text):
        if not text.startswith(self.label):
            # Might still correspond to a different Description.
            return None
        text = text[len(self.label):]
        # Is this the short form with an annotation not required?
        if (self.lowest == self.highest) and not text:
            return self.lowest
        # If the annotation isn't present, flag an error.
        # This means that if one label for a Field value is a substring of
        # another, the longer one needs to be checked first.
        if not (text.startswith('(') and text.endswith(')')):
            raise ValueError('Missing offset for labelled range')
        value = int(text[1:-1], 0) + self.lowest
        if value < self.lowest or value > self.highest:
            raise ValueError('Invalid offset for labelled range')
        return value


class RangeDescription:
    def __init__(self, lowest, highest, numeric_formatter):
        self.lowest = lowest
        self.highest = highest
        self.numeric_formatter = numeric_formatter
        # When parsing, any base is allowed with the appropriate prefix.


    def __str__(self):
        low = self.numeric_formatter(self.lowest)
        high = self.numeric_formattter(self.highest)
        if self.lowest == self.highest:
            return f'RangeDescription: {low}'
        else:
            return f'RangeDescription: {low} .. {high}'


    def format(self, value):
        if value < self.lowest or value > self.highest:
            # Might still be representable another way.
            return None
        return self.numeric_formatter(value)


    def parse(self, text):
        try:
            value = int(text, 0)
        except ValueError:
            # Might still correspond to a different Description.
            return None
        # If the value is out of range, it might *still* correspond
        # to a different Description (for another range).
        return value if self.lowest <= value <= self.highest else None


class FlagsDescription:
    def __init__(self, names):
        self.names = names


    def __str__(self):
        return f"FlagsDescription: {' | '.join(self.names)}"


    def format(self, value):
        set_flags = []
        for i, name in enumerate(self.names):
            if value & (1 << i):
                set_flags.append(name)
        return ' | '.join(set_flags)


    def parse(self, text):
        value = 0
        items = [t.strip() for t in text.split('|')]
        set_flags = set(items)
        if len(items) != len(set_flags):
            raise ValueError('Duplicate flag names not allowed')
        for i, name in enumerate(self.names):
            if name in set_flags:
                value |= 1 << i
                set_flags.remove(name)
        # If there were names left over, this data might still
        # correspond to a different Description. This happens
        # in particular when there was only a single name.
        return None if set_flags else value


class Field:
    def __init__(self, name, bits, bias, signed, fixed, descriptions):
        # The bias is added when assembling, deducted when disassembling.
        self.name = name
        self.bits = bits
        self.bias = bias
        self.signed = signed
        self.fixed = fixed
        self.descriptions = descriptions


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
        return (self.count if self.signed else self.halfcount) - 1 - self.bias


    # Convert unsigned value from the data into one that will be formatted.
    def value(self, raw):
        assert 0 <= raw < self.count
        if signed and raw >= self.halfcount:
            raw -= self.count
        return raw - self.bias


    # Convert value computed from parsing into one stored in the data.
    def raw(self, value):
        if not self.minimum <= value <= self.maximum:
            raise ValueError(
                f'{value} out of range {self.minimum}..{self.maximum}'
            )
        value += self.bias
        if signed and value < 0:
            assert value >= -self.halfcount
            value += self.count
        assert 0 <= value < self.count
        return value


    def __str__(self):
        low, high, base = self.minimum, self.maximum
        return f'Field {self.name} {{range: {low}..{high}}}'


    def throw(self, msg):
        raise ValueError(f'Field {self.name}: {msg}')


    def format(self, raw):
        value = self.value(raw)
        if self.fixed is not None:
            if value != self.fixed:
                self.throw(
                    f'Expected value {self.fixed} in data; actually {value}'
                )
            # The parent Option should filter this out
            return None
        for description in self.descriptions:
            try:
                result = description.format(text)
            except ValueError as e:
                self.throw(e)
            if result is not None:
                return result
        # No exceptions, but nothing worked
        self.throw(f'No valid format for value: {value}')
    
    
    def parse(self, text):
        if self.fixed is not None:
            # This value should get hacked in by the parent Option
            assert text is None
            return self.raw(self.fixed)
        for description in self.descriptions:
            try:
                result = description.parse(text)
            except ValueError as e:
                self.throw(e)
            if result is not None:
                return self.raw(result)
        # No exceptions, but nothing worked
        self.throw(f"Couldn't parse: '{text}'")


class Option:
    def __init__(self, fields, fixed_positions):
        self.fields = fields
        self.fixed_positions = fixed_positions


    @property
    def arguments(self):
        return len(fields) - len(self.fixed_positions)


    def format(self, full_value):
        bit = 0
        results = []
        for i, field in enumerate(self.fields):
            skip = i in self.fixed_positions
            bits = field.bits
            # TODO: think about how to support other endianness.
            raw = full_value & ((1 << bits) - 1)
            full_value >>= field.bits
            result = field.format(raw)
            assert skip == (result is None)
            if not skip:
                results.append(result)
        return results


    def parse(self, items):
        bit = 0
        value = 0
        assert len(items) == self.arguments
        item_source = iter(items)
        for i, field in enumerate(self.fields):
            skip = i in self.fixed_positions
            item = None if skip else next(item_source)
            result = field.parse(item)
            assert 0 <= result < (1 << field.bits)
            value |= result << bit
            bit += field.bits
        return result


class Type:
    # All constraints to be verified in an external process.
    # Do not call this constructor directly.
    def __init__(self, name, size, format_option, option_map):
        self.name = name
        self.size = size
        self.format_option = format_option
        self.option_map = option_map


    def format(self, value):
        # Exceptions will be propagated to the Struct level.
        return self.format_option.format(int.from_bytes(value, 'little'))


    def parse(self, items):
        try:
            parser = self.option_map[len(items)]
        except KeyError:
            raise ValueError(
                'Invalid number of parameters for {self.name} type'
            )
        return parser.parse(items).to_bytes(self.size // 8, 'little')
