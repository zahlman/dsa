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
            raise ValueError('invalid fixed data during formatting')
        # Collect results for each field.
        # TODO: think about how to support other endianness.
        return [
            field.format((full_value >> offset) & ((1 << field.size) - 1))
            for offset, field in zip(self.offsets, self.fields)
        ]


    def parse(self, items):
        # Logically this should combine all the fields with bitwise-or rather
        # than addition; but if the fields overlap then there is a bug
        # somewhere else anyway.
        return self.fixed_value | sum(
            field.parse(item) << offset
            for field, item, offset in zip(self.fields, items, self.offsets)
        )


def collect(items):
    result = ', '.join(items)
    if result != ''.join(result.split()): # embedded whitespace
        result = f'[{result}]'
    return result


def itemize(raw):
    # N.B. Even if there's no whitespace, there could still be multiple params.
    return [x.strip() for x in raw.split(',')]


class Member:
    # All constraints to be verified in an external process.
    # Do not call this constructor directly.
    def __init__(self, typename, name, size, format_option, option_map, doc):
        self.typename = typename
        self.name = name
        self.size = size # byte count!
        self.format_option = format_option
        self.option_map = option_map
        self.doc = doc # Unused for now.


    def __str__(self):
        return f'{self.name} of type {self.typename}'


    def throw(self, msg):
        raise ValueError(f'member {self.name}: {msg}')


    def format(self, value):
        try:
            return collect(
                self.format_option.format(int.from_bytes(value, 'little'))
            )
        except ValueError as e:
            self.throw(e)


    def parse(self, raw):
        items = itemize(raw)
        try:
            parser = self.option_map[len(items)]
        except KeyError:
            self.throw(
                f'Invalid number of parameters for {self.typename} type'
            )
        try:
            return parser.parse(items).to_bytes(self.size, 'little')
        except ValueError as e:
            self.throw(e)


def _sorted_option_fields(field_makers, deferred):
    # No doc is associated at the Option level.
    # TODO: implement custom ordering.
    return [f(deferred) for f in field_makers]


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


def _parameterize(typename, deferred):
    parameters = sorted(f'{k}={v}' for k, v in deferred.items())
    return f"{typename}({', '.join(parameters)})"


def _member(field_maker_groups, typename, doc, deferred, name):
    format_option = None
    option_map = {}
    size = None
    for field_makers in field_maker_groups:
        o_size, option = _option(field_makers, deferred)
        if size is None:
            size = o_size
        elif size != o_size:
            raise ValueError(
                'inconsistent bit size for member'
            )
        if option.arguments in option_map:
            raise ValueError(
                'formats for member must have all different argument counts'
            )
        option_map[option.arguments] = option
        if format_option is None:
            format_option = option
    if format_option is None:
        raise ValueError('no formatting options provided for member')
    typename = _parameterize(typename, deferred)
    return Member(typename, name, size, format_option, option_map, doc)


def member_maker(typename, field_makers, doc):
    return partial(_member, field_makers, typename, doc)
