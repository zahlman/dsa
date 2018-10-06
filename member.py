from field import make_field
from functools import partial


class Option:
    def __init__(self, offsets, fields, fixed_mask, fixed_value, size):
        self.offsets = offsets
        self.fields = fields
        self.fixed_mask = fixed_mask
        self.fixed_value = fixed_value
        self.size = size


    @property
    def arguments(self):
        return len(self.fields)


    def format(self, full_value, disassembler, member_name):
        if (full_value & self.fixed_mask) != self.fixed_value:
            return None # try the next Option.
        # Collect results for each field.
        # TODO: think about how to support other endianness.
        return [
            field.format(
                (full_value >> offset) & ((1 << field.size) - 1),
                disassembler, f'{member_name}'
            )
            for offset, field in zip(
                self.offsets, self.fields
            )
        ]


    def parse(self, items):
        # Logically this should combine all the fields with bitwise-or rather
        # than addition; but if the fields overlap then there is a bug
        # somewhere else anyway.
        return self.fixed_value | sum(
            field.parse(item) << offset
            for field, item, offset in zip(self.fields, items, self.offsets)
        )


def _collect(items):
    result = ', '.join(items)
    if result != ''.join(result.split()): # embedded whitespace
        result = f'[{result}]'
    return result


def _itemize(raw):
    # N.B. Even if there's no whitespace, there could still be multiple params.
    return [x.strip() for x in raw.split(',')]


def _build_option_map(options):
    result = {}
    sizes = set()
    for option in options:
        count = option.arguments
        sizes.add(option.size)
        if count in result:
            raise ValueError('Options must have unique argument counts')
        result[count] = option
    if len(sizes) > 1:
        raise ValueError('Inconsistent Option sizes')
    try:
        return sizes.pop(), result
    except KeyError:
        raise ValueError('Must have at least one Option')


class Member:
    def __init__(self, typename, options):
        # member "name" will be handled at the struct level.
        self.typename = typename
        self.options = options
        self.size, self.option_map = _build_option_map(options)


    def format(self, value, disassembler, name):
        for option in self.options:
            result = option.format(
                int.from_bytes(value, 'little'), disassembler, name
            )
            if result is not None:
                return _collect(result)
        raise ValueError("couldn't format data (no matching Option)")


    def parse(self, raw):
        items = _itemize(raw)
        try:
            parser = self.option_map[len(items)]
        except KeyError:
            raise ValueError(
                f'Invalid number of parameters for {self.typename} type'
            )
        return parser.parse(items).to_bytes(self.size, 'little')


class OptionLSM:
    def __init__(self):
        self.field_makers = []


    def add_line(self, line_tokens):
        self.field_makers.append(partial(make_field, line_tokens))


    def result(self, description_lookup):
        position, fixed_mask, fixed_value = 0, 0, 0
        offsets, fields = [], []
        for maker in self.field_makers:
            name, field, fixed, bits = maker(description_lookup)
            if fixed is not None:
                mask = (1 << bits) - 1
                fixed_mask |= mask << position
                assert 0 <= fixed <= mask
                fixed_value |= fixed << position
            else:
                offsets.append(position)
                fields.append(field)
            position += bits
        size, remainder = divmod(position, 8)
        if remainder:
            raise ValueError('option size must be a multiple of 8 bits')
        return Option(
            offsets, fields, fixed_mask, fixed_value, size
        )


class MemberLSM:
    def __init__(self):
        self.option_names = []


    def add_line(self, line_tokens):
        name, *junk = line_tokens
        if junk:
            raise ValueError('junk data after option name')
        self.option_names.append(name)


    def result(self, typename, option_lookup):
        return Member(
            typename, [option_lookup[o] for o in self.option_names]
        )
