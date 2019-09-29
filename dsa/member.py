from .errors import SequenceError, UserError
from .field import field_arguments, make_field, member_field_data
from .parsing.line_parsing import integer, TokenError, TupleError


class BAD_FIXED_VALUE(SequenceError):
    """data had incorrect fixed value"""


class BAD_VALUE_HEADER(UserError):
    """invalid extra data for Value"""


class INVALID_POINTER(TupleError):
    """missing info for Pointer"""


class INVALID_PARAMETER_COUNT(UserError):
    """{need} parameters required (got {got})"""


class INVALID_MEMBER_SIZE(UserError):
    """size of data represented by type must be a multiple of 8 bits"""


class BAD_POINTER_SIZE(UserError):
    """pointer size in bits must be a multiple of 8"""


def _extract(value, offset, size):
    # TODO: handle big-endian here.
    return (value >> offset) & ((1 << size) - 1)


class Value:
    def __init__(
        self, typename, offsets, fields, fixed_mask, fixed_value, size
    ):
        # 'name' stored at Struct level and injected when needed.
        self._typename = typename
        self.offsets = offsets
        self.fields = fields
        self.fixed_mask = fixed_mask
        self.fixed_value = fixed_value
        self._size = size


    @property
    def size(self):
        return self._size # read-only


    @property
    def typename(self):
        return self._typename # read-only


    def pointer_value(self, value):
        return None # cannot point at anything.


    def _raw_values(self, value):
        value = int.from_bytes(value, 'little')
        # Should be impossible? pre-verified by regex?
        BAD_FIXED_VALUE.require(
            (value & self.fixed_mask) == self.fixed_value
        )
        for offset, field in zip(self.offsets, self.fields):
            yield field, _extract(value, offset, field.size)


    def format(self, value, lookup):
        # lookup is irrelevant; we don't have a pointer
        return ', '.join(
            field.format(raw)
            for field, raw in self._raw_values(value)
        )


    def parse(self, items):
        expected = len(self.fields)
        actual = len(items)
        INVALID_PARAMETER_COUNT.require(
            expected == actual, need=expected, got=actual
        )
        result = self.fixed_value
        for offset, field, item in zip(self.offsets, self.fields, items):
            result |= field.parse(item) << offset
        return result.to_bytes(self.size, 'little')


class ValueLoader:
    def __init__(self, tokens):
        BAD_VALUE_HEADER.require(not tokens)
        self.field_data = []


    def add_line(self, line_tokens):
        self.field_data.append(member_field_data(line_tokens))


    def result(self, typename, description_lookup):
        position, fixed_mask, fixed_value = 0, 0, 0
        offsets, fields = [], []
        for name, args, fixed, bits in self.field_data:
            field = make_field(bits, args, description_lookup)
            if fixed is not None:
                fixed = field.parse(fixed)
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
        return Value(
            typename, offsets, fields, fixed_mask, fixed_value, size
        )


class Pointer:
    def __init__(self, typename, field):
        # 'name' stored at Struct level and injected when needed.
        self._typename = typename
        self._field = field


    @property
    def size(self):
        return self._field.size // 8 # read-only


    @property
    def typename(self):
        return self._typename


    def pointer_value(self, value):
        return self._field.pointer_value(int.from_bytes(value, 'little'))


    def format(self, value, lookup):
        numeric = int.from_bytes(value, 'little')
        # TODO: avoid repeating this check.
        return (
            self._field.format(numeric)
            if self.pointer_value(value) is None
            else lookup(self._field.bias(numeric))
        )


    def parse(self, items):
        INVALID_PARAMETER_COUNT.require(len(items)==1, need=1, got=len(items))
        return self._field.parse(items[0]).to_bytes(self.size, 'little')


class PointerLoader:
    def __init__(self, tokens):
        # The typename for the Pointer was already extracted from the `tokens`.
        # It will be specified later.
        size, tokens = INVALID_POINTER.shift(tokens)
        self._bits = integer(size)
        octets, leftover = divmod(self._bits, 8)
        BAD_POINTER_SIZE.require(not leftover)
        self._args = field_arguments(tokens)
        # TODO: added lines represent filters applied to the pointed-at data.


    def add_line(self, line_tokens):
        # TODO
        pass


    def result(self, typename, description_lookup):
        # TODO: create filters from accumulated lines?
        return Pointer(
            typename, make_field(self._bits, self._args, description_lookup)
        )
