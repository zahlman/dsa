from ..errors import MappingError, UserError
from ..structs import Struct, StructGroup
from .file_parsing import SimpleLoader
from .line_parsing import arguments, boolean, hexdump, one_of, positive_integer, TupleError, TokenError
from collections import OrderedDict


class INVALID_STRUCT_NAME(TokenError):
    """struct name must be single-part (has {actual} parts)"""


class NEXT_LAST_CONFLICT(UserError):
    """`next` and `last` options are mutually exclusive"""


class BAD_MEMBER(TupleError):
    """not enough or too many tokens for member specification"""


class INVALID_TF(TupleError):
    # Should be impossible?
    """invalid typename/fixed data"""


class BAD_REFERENT(TupleError):
    """invalid specification for pointer referent"""


class UNRECOGNIZED_TYPE(MappingError):
    """unrecognized type {key}"""


class NOT_FIXED_OR_NAMED(TupleError):
    """member must have either a name or a fixed value"""


class DUPLICATE_STRUCT(MappingError):
    """duplicate struct definition for {key}"""


class MEMBER_OUTSIDE_STRUCT(UserError):
    """member definition outside of struct"""


class NO_OPTIONS(UserError):
    """empty struct group definition (no option line)"""


class NO_STRUCTS(UserError):
    """empty struct group definition (no structs)"""


class DUPLICATE_GROUP(MappingError):
    """duplicate definition for struct group `{key}`"""


def parse_options(line_tokens):
    return arguments(line_tokens, {
        'align': (positive_integer, 1),
        'endian': one_of('big', 'little'),
        'first': (set, None),
        'count': (positive_integer, None),
        'terminator': (hexdump, None)
    })


def parse_struct_header(line_tokens):
    name, *flag_tokens = line_tokens # TODO: support for aliases
    name, = INVALID_STRUCT_NAME.pad(name, 1, 1)
    options = arguments(
        flag_tokens, {'next': (set, None), 'last': (boolean, False)}
    )
    if options.last:
        NEXT_LAST_CONFLICT.require(options.next is None)
        return name, set()
    # If nothing is specified, the None value is passed through and will be
    # replaced later with a set of all possibilities.
    return name, options.next


class StructData:
    def __init__(self, line_tokens, alignment):
        self._name, self._followers = parse_struct_header(line_tokens)
        self._data = []
        self._alignment = alignment


    @property
    def name(self):
        return self._name


    @property
    def followers(self):
        return self._followers


    @property
    def struct(self):
        return Struct(self._data, self._alignment)


    def add_member(self, tokens, types):
        typename, tokens = BAD_MEMBER.shift(tokens)
        typename, fixed = INVALID_TF.shift(typename)
        member = UNRECOGNIZED_TYPE.get(types, typename)
        ref_name = None
        if not fixed: # should be an empty list
            fixed = None # normalize
            name, tokens = NOT_FIXED_OR_NAMED.shift(tokens)
            name = INVALID_STRUCT_NAME.singleton(name)
            if tokens:
                ref_token, tokens = BAD_MEMBER.shift(tokens)
                BAD_MEMBER.require(not tokens)
                tag, ref_name = BAD_REFERENT.shift(ref_token)
                ref_name, junk = BAD_REFERENT.shift(ref_name)
                BAD_REFERENT.require(not junk)
                BAD_REFERENT.require(tag == 'referent')
        else:
            BAD_MEMBER.require(not tokens)
            name = None
            fixed = member.parse(fixed)
        self._data.append((member, name, fixed, ref_name))


class StructGroupLoader(SimpleLoader):
    def __init__(self, types):
        self._types = types # type lookup used to create members
        self._struct_name = None
        self._options = None
        self._struct_data = OrderedDict()


    def unindented(self, tokens):
        if self._options is None:
            self._options = parse_options(tokens)
        else:
            data = StructData(tokens, self._options.align)
            DUPLICATE_STRUCT.add_unique(self._struct_data, data.name, data)
            self._struct_name = data.name


    def indented(self, tokens):
        MEMBER_OUTSIDE_STRUCT.require(self._struct_name is not None)
        self._struct_data[self._struct_name].add_member(tokens, self._types)


    def result(self):
        NO_OPTIONS.require(self._options is not None)
        data = self._struct_data
        NO_STRUCTS.require(len(data) > 0)
        # FIXME: Is order preservation actually necessary?
        return StructGroup(
            OrderedDict(
                (name, datum.struct) for name, datum in data.items()
            ),
            OrderedDict(
                (name, datum.followers) for name, datum in data.items()
            ),
            self._options
        )
