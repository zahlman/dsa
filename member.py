import errors
from field import make_field
from line_parsing import TokenError
from functools import partial


class NONUNIQUE_ARGUMENT_COUNTS(errors.MappingError):
    """multiple `option`s found with {key} arguments"""


class INCONSISTENT_MEMBER_SIZE(errors.UserError):
    """`option`s must all have the same total size"""


class NO_OPTIONS(errors.UserError):
    """must have at least one `option`"""


class NO_MATCHING_OPTION(errors.SequenceError):
    """data doesn't match any option for formatting"""


class INVALID_PARAMETER_COUNT(errors.MappingError):
    """no formatting `option` uses {key} parameters"""


class INVALID_OPTION_SIZE(errors.UserError):
    """`option` size must be a multiple of 8 bits"""


class BAD_OPTION(TokenError):
    """junk data after option name"""


class BAD_OPTION_NAME(TokenError):
    """option name token must be single-part (has {actual} parts)"""


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


def _build_option_map(options):
    result = {}
    sizes = set()
    for option in options:
        count = option.arguments
        sizes.add(option.size)
        NONUNIQUE_ARGUMENT_COUNTS.add_unique(result, count, option)
    INCONSISTENT_MEMBER_SIZE.require(len(sizes) <= 1)
    NO_OPTIONS.require(len(sizes) >= 1)
    return sizes.pop(), result


class Member:
    def __init__(self, typename, options):
        # member "name" will be handled at the struct level.
        self.typename = typename
        self.options = options
        self.size, self.option_map = _build_option_map(options)


    def _format(self, value, disassembler, name):
        # The disassembler will wrap these tokens in [] if needed and clean
        # up the final output.
        return ', '.join(NO_MATCHING_OPTION.first_not_none(
            option.format(
                int.from_bytes(value, 'little'), disassembler, name
            )
            for option in self.options
        ))


    def format(self, value, disassembler, name):
        return errors.wrap(
            f'Member {name} (of type {self.typename})',
            self._format, value, disassembler, name
        )


    def _parse(self, subtokens):
        parser = INVALID_PARAMETER_COUNT.get(self.option_map, len(subtokens))
        return parser.parse(subtokens).to_bytes(self.size, 'little')


    def parse(self, subtokens, name):
        return errors.wrap(
            f'Member {name} (of type {self.typename})',
            self._parse, subtokens
        )


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
        INVALID_OPTION_SIZE.require(not remainder)
        return Option(
            offsets, fields, fixed_mask, fixed_value, size
        )


class MemberLSM:
    def __init__(self):
        self.option_names = []


    def add_line(self, line_tokens):
        name, = BAD_OPTION.pad(line_tokens, 1, 1)
        name, = BAD_OPTION_NAME.pad(name, 1, 1)
        self.option_names.append(name)


    def result(self, typename, option_lookup):
        return Member(
            typename, [option_lookup[o] for o in self.option_names]
        )
