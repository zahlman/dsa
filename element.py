from functools import partial


class Option:
    def __init__(self, offsets, fields, fixed_mask, fixed_value):
        self.offsets = offsets
        self.fields = fields
        self.fixed_mask = fixed_mask
        self.fixed_value = fixed_value


    @property
    def arguments(self):
        return len(self.fields)


    def format(self, full_value):
        # Validate fixed value.
        # Only one Option will be tried for formatting, so raise an exception
        # if validation fails.
        if (full_value & self.fixed_mask) != self.fixed_value:
            raise ValueError('invalid fixed data for element')
        # Collect results for each field.
        # TODO: think about how to support other endianness.
        result = ', '.join(
            field.format((full_value >> offset) & ((1 << field.size) - 1))
            for offset, field in zip(self.offsets, self.fields)
        )
        if result != ''.join(result.split()): # embedded whitespace
            result = f'[{result}]'
        return result


    def parse(self, items):
        # Logically this should combine all the fields with bitwise-or rather
        # than addition; but if the fields overlap then there is a bug
        # somewhere else anyway.
        return self.fixed_value | sum(
            field.parse(item) << offset
            for field, item, offset in zip(self.fields, items, self.offsets)
        )


class Element:
    # All constraints to be verified in an external process.
    # Do not call this constructor directly.
    def __init__(self, name, size, format_option, option_map, doc):
        self.name = name
        self.size = size # byte count!
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
        return parser.parse(items).to_bytes(self.size, 'little')


def _sorted_option_fields(field_makers, deferred):
    # No doc is associated at the Option level.
    raw_fields = []
    for f in field_makers:
        order, field = f(deferred)
        if order is None:
            raw_fields.append(field)
        else:
            raw_fields.insert(order, field)
    return raw_fields


def _prepared_option_fields(raw_fields):
    position, offsets, fields, fixed_mask, fixed_value = 0, [], [], 0, 0
    for f in raw_fields:
        size = f.size
        if f.is_fixed:
            mask = (1 << size) - 1
            fixed_mask |= mask << position
            assert 0 <= f.raw <= mask
            fixed_value |= f.raw << position
        else:
            offsets.append(position)
            fields.append(f)
        position += size
    return position, offsets, fields, fixed_mask, fixed_value


def _option(field_makers, deferred):
    raw_fields = _sorted_option_fields(field_makers, deferred)
    option_size, *option_data = _prepared_option_fields(raw_fields)
    if option_size % 8:
        raise ValueError('option size must be a multiple of 8 bits')
    return option_size // 8, Option(*option_data)


def _element(field_maker_groups, name, doc, deferred):
    format_option = None
    option_map = {}
    size = None
    for field_makers in field_maker_groups:
        o_size, option = _option(field_makers, deferred)
        if size is None:
            size = o_size
        elif size != o_size:
            raise ValueError(
                'options for element must have the same total size'
            )
        if option.arguments in option_map:
            raise ValueError(
                'options for element must have all different argument counts'
            )
        option_map[option.arguments] = option
        if format_option is None:
            format_option = option
    if format_option is None:
        raise ValueError('no options provided for element')
    return Element(name, size, format_option, option_map, doc)


def element_maker(name, field_makers, doc):
    return partial(_element, field_makers, name, doc)
