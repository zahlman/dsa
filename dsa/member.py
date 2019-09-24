from . import errors
from .field import make_field
from .parsing.line_parsing import TokenError
from functools import partial


class BAD_FIXED_VALUE(errors.SequenceError):
    """data had incorrect fixed value"""


class INVALID_PARAMETER_COUNT(errors.UserError):
    """{need} parameters required (got {got})"""


class INVALID_MEMBER_SIZE(errors.UserError):
    """size of data represented by type must be a multiple of 8 bits"""


def _extract(value, offset, size):
    # TODO: handle big-endian here.
    return (value >> offset) & ((1 << size) - 1)


class Member:
    def __init__(
        self, typename, offsets, fields, fixed_mask, fixed_value, size
    ):
        # 'name' stored at Struct level and injected when needed.
        self.typename = typename
        self.offsets = offsets
        self.fields = fields
        self.fixed_mask = fixed_mask
        self.fixed_value = fixed_value
        self._size = size


    @property
    def size(self):
        return self._size # read-only


    def _tag(self, name):
        return f'Member `{name}` (of type `{self.typename}`)'


    def _raw_values(self, value):
        value = int.from_bytes(value, 'little')
        BAD_FIXED_VALUE.require(
            (value & self.fixed_mask) == self.fixed_value
        )
        for offset, field in zip(self.offsets, self.fields):
            yield field, _extract(value, offset, field.size)


    def _referents(self, value, name):
        return [
            referent
            for field, raw in self._raw_values(value)
            for referent in field.referents(raw, name)
        ]


    def referents(self, name, value):
        result = errors.wrap(self._tag(name), self._referents, value, name)
        return result


    def _format(self, value, labels):
        return ', '.join(
            field.format(raw, labels)
            for field, raw in self._raw_values(value)
        )


    def format(self, name, value, labels):
        return errors.wrap(self._tag(name), self._format, value, labels)


    def _parse(self, items):
        expected = len(self.fields)
        actual = len(items)
        INVALID_PARAMETER_COUNT.require(
            expected == actual, need=expected, got=actual
        )
        result = self.fixed_value
        for offset, field, item in zip(self.offsets, self.fields, items):
            result |= field.parse(item) << offset
        return result.to_bytes(self._size, 'little')


    def parse(self, name, items):
        return errors.wrap(
            self._tag(name), self._parse, items
        )


class MemberLoader:
    def __init__(self):
        self.field_makers = []


    def add_line(self, line_tokens):
        self.field_makers.append(partial(make_field, line_tokens))


    def result(self, typename, description_lookup):
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
        INVALID_MEMBER_SIZE.require(not remainder)
        return Member(
            typename, offsets, fields, fixed_mask, fixed_value, size
        )
