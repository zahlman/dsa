from ..errors import MappingError, UserError
from ..structs import Struct, StructGroup
from .line_parsing import arguments, boolean, hexdump, one_of, positive_integer, TokenError
from collections import OrderedDict


class INVALID_STRUCT_NAME(TokenError):
    """struct name must be single-part (has {actual} parts)"""


class NEXT_LAST_CONFLICT(UserError):
    """`next` and `last` options are mutually exclusive"""


class INVALID_TNF(UserError):
    """invalid typename/name/fixed data"""


class UNRECOGNIZED_TYPE(MappingError):
    """unrecognized type {key}"""


class NOT_FIXED_OR_NAMED(UserError):
    """member must have either a name or a fixed value"""


class FIXED_AND_NAMED(UserError):
    """member with fixed value may not be named"""


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
        self.name, self.followers = parse_struct_header(line_tokens)
        self.member_data = []
        self.alignment = alignment


    def create(self):
        return (
            self.name,
            Struct(self.member_data, self.alignment),
            self.followers
        )


    def add_member(self, line_tokens, types):
        tnf, *options = line_tokens
        # Any parts after the second are interpreted as a fixed-value token.
        try:
            typename, name, *fixed = tnf
        except ValueError:
            raise INVALID_TNF
        member = UNRECOGNIZED_TYPE.get(types, typename)
        if not fixed:
            NOT_FIXED_OR_NAMED.require(name != '')
            fixed = None # normalize for later use
        else:
            FIXED_AND_NAMED.require(name == '')
            fixed = member.parse(name, fixed)
        self.member_data.append((member, name, fixed))


class StructGroupLoader:
    def __init__(self, types):
        self.types = types
        self._reset()


    def _reset(self):
        self.structs = OrderedDict()
        self.options = None
        self.struct_data = None
        self.graph = OrderedDict()


    def _push_old_struct(self):
        if self.struct_data is None:
            return
        name, struct, followers = self.struct_data.create()
        DUPLICATE_STRUCT.add_unique(self.structs, name, struct)
        self.graph[name] = followers
        self.struct_data = None


    def _continue_struct(self, line_tokens):
        MEMBER_OUTSIDE_STRUCT.require(self.struct_data is not None)
        self.struct_data.add_member(line_tokens, self.types)


    def _new_struct(self, line_tokens):
        self._push_old_struct()
        self.struct_data = StructData(line_tokens, self.options.align)


    def add_line(self, indent, line_tokens):
        if indent:
            self._continue_struct(line_tokens)
        elif self.options is None:
            self.options = parse_options(line_tokens)
        else:
            self._new_struct(line_tokens)


    def end_file(self, label, accumulator):
        NO_OPTIONS.require(self.options is not None)
        self._push_old_struct()
        NO_STRUCTS.require(bool(self.structs))
        DUPLICATE_GROUP.add_unique(
            accumulator, label, StructGroup(
                self.structs, self.graph, self.options
            )
        )
        self._reset()
