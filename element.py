class Option:
    def __init__(self, fields, fixed_positions):
        self.fields = fields
        self.fixed_positions = fixed_positions


    @property
    def arguments(self):
        return len(self.fields) - len(self.fixed_positions)


    def format(self, full_value):
        bit = 0
        results = []
        for i, field in enumerate(self.fields):
            skip = i in self.fixed_positions
            bits = field.size
            # TODO: think about how to support other endianness.
            raw = full_value & ((1 << bits) - 1)
            full_value >>= bits 
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
            assert 0 <= result < (1 << field.size)
            value |= result << bit
            bit += field.size
        return value


class Type:
    # All constraints to be verified in an external process.
    # Do not call this constructor directly.
    def __init__(self, name, size, format_option, option_map, doc):
        self.name = name
        self.size = size
        self.format_option = format_option
        self.option_map = option_map
        self.doc = doc # Unused for now.


    def format(self, value):
        # Exceptions will be propagated to the Struct level.
        return self.format_option.format(int.from_bytes(value, 'little'))


    def parse(self, items):
        try:
            parser = self.option_map[len(items)]
        except KeyError:
            raise ValueError(
                f'Invalid number of parameters for {self.name} type'
            )
        return parser.parse(items).to_bytes(self.size // 8, 'little')


def make_option(field_builders, deferred):
    # No doc is associated at the Option level.
    fields = []
    fixed_mask = []
    size = 0
    for builder in field_builders:
        order, field_size, is_fixed, field = builder(deferred)
        size += field_size
        if order is None:
            fields.append(field)
            fixed_mask.append(is_fixed)
        else:
            fields.insert(order, field)
            fixed_mask.insert(order, is_fixed)
    return size, Option(fields, [i for i, f in enumerate(fixed_mask) if f])


def make_type(option_builders, name, doc, deferred):
    format_option = None
    option_map = {}
    size = None
    for builder in option_builders:
        o_size, option = builder(deferred)
        if size is None:
            size = o_size
        elif size != o_size:
            raise ValueError('options for type must have the same total size')
        if option.arguments in option_map:
            raise ValueError(
                'options for type must have all different argument counts'
            )
        option_map[option.arguments] = option
        if format_option is None:
            format_option = option
    if format_option is None:
        raise ValueError('no options provided for type')
    return Type(name, size, format_option, option_map, doc)
