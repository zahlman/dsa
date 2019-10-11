from .errors import SequenceError, UserError
from .field import member_field_data, numeric_field_maker
from .parsing.line_parsing import argument_parser, line_parser
from .parsing.token_parsing import single_parser
from functools import partial


class BAD_SPECS(UserError):
    """additional type parameter(s) `{keys}` not valid for {kind} member of type `{typename}`"""


class BAD_FIXED_VALUE(SequenceError):
    """data had incorrect fixed value"""


class BAD_VALUE_HEADER(UserError):
    """invalid extra data for Value"""


class INVALID_PARAMETER_COUNT(UserError):
    """{need} parameters required (got {got})"""


class INVALID_MEMBER_SIZE(UserError):
    """size of data represented by type must be a multiple of 8 bits"""


def _extract(value, offset, size):
    # TODO: handle big-endian here.
    # TODO: require that text fields are aligned to a byte boundary?
    # TODO: ensure text fields are aware of being given a big-endian value.
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


    def pointer_value(self, value, label):
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
        return tuple(
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


def _make_value(
    typename, offsets, fields, fixed_mask, fixed_value, size, member_specs
):
    keys = set(member_specs.keys())
    BAD_SPECS.require(not keys, keys=keys, kind='compound', typename=typename)
    return Value(typename, offsets, fields, fixed_mask, fixed_value, size)


class ValueLoader:
    def __init__(self, tokens):
        BAD_VALUE_HEADER.require(not tokens)
        self.field_data = []


    def add_line(self, line_tokens):
        self.field_data.append(member_field_data(line_tokens))


    def result(self, typename, description_lookup):
        position, fixed_mask, fixed_value = 0, 0, 0
        offsets, fields = [], []
        for name, make_field, fixed, bits in self.field_data:
            field = make_field(description_lookup)
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
        return partial(
            _make_value,
            typename, offsets, fields, fixed_mask, fixed_value, size
        )


class Pointer:
    def __init__(self, typename, filter_specs, field, referent_args):
        self._typename = typename
        self._filter_specs = filter_specs
        self._field = field
        # a list of strings with the referent name and config parameters.
        self._referent_args = referent_args


    @property
    def size(self):
        return self._field.size // 8 # read-only


    @property
    def typename(self):
        return self._typename


    def _pointer_value(self, numeric):
        return self._field.pointer_value(numeric)


    def pointer_value(self, value, label):
        value = self._pointer_value(int.from_bytes(value, 'little'))
        return None if value is None else (
            self._referent_args, self._filter_specs, value, label
        )


    def format(self, value, lookup):
        numeric = int.from_bytes(value, 'little')
        # TODO: avoid repeating this check.
        return (
            self._field.format(numeric)
            if self._pointer_value(numeric) is None
            else lookup(self._field.bias(numeric))
        ),


    def parse(self, items):
        INVALID_PARAMETER_COUNT.require(len(items)==1, need=1, got=len(items))
        return self._field.parse(items[0]).to_bytes(self.size, 'little')


def _make_pointer(typename, filter_specs, type_specs, lookup, member_specs):
    params, bits = type_specs
    params.update(member_specs)
    field = numeric_field_maker(params, bits)(lookup)
    BAD_SPECS.require(
        'encoding' not in params,
        keys={'encoding'}, kind='pointer', typename=typename
    )
    # multipart token: interpreter name + hidden config params
    referent_name = params.get('referent', None)
    return Pointer(typename, filter_specs, field, referent_name)


_pointer_size_parser = line_parser(
    'pointer section header',
    single_parser('size (in bits)', 'fieldsize'),
    # 2 parameters - the `pointer` keyword and name - were handled by
    # the TypeLoader already.
    required=1, extracted=2, more=True
)


# Like the arguments for a Field, but with `referent` instead of `encoding`.
_pointer_argument_parser = argument_parser(
    bias='integer', stride='positive', values='string',
    signed={None: True, 'true': True, 'false': False},
    base={'2': bin, '8': oct, '10': str, '16': hex},
    referent='[string'
)


class PointerLoader:
    def __init__(self, tokens):
        # The typename for the Pointer was already extracted from the `tokens`.
        # It will be specified later.
        bits, tokens = _pointer_size_parser(tokens)
        self._specs = _pointer_argument_parser(tokens), bits
        self._filter_specs = []


    def add_line(self, line_tokens):
        self._filter_specs.append(line_tokens)


    def result(self, typename, description_lookup):
        return partial(
            _make_pointer,
            typename, self._filter_specs, self._specs, description_lookup
        )
