from arguments import boolean, hexdump, parameters, positive_integer, one_of
import errors
from parse_config import parts_of
from structs import Struct, StructGroup
from collections import OrderedDict


class NEXT_LAST_CONFLICT(errors.UserError):
    """`next` and `last` options are mutually exclusive"""


class UNRECOGNIZED_TYPE(errors.MappingError):
    """unrecognized type {key}"""


class NOT_FIXED_OR_NAMED(errors.UserError):
    """member must have either a name or a fixed value"""


class FIXED_AND_NAMED(errors.UserError):
    """member with fixed value may not be named"""


class DUPLICATE_STRUCT(errors.MappingError):
    """duplicate struct definition for {key}"""


class MEMBER_OUTSIDE_STRUCT(errors.UserError):
    """member definition outside of struct"""


class NO_OPTIONS(errors.UserError):
    """empty struct group definition (no option line)"""


class NO_STRUCTS(errors.UserError):
    """empty struct group definition (no structs)"""


class DUPLICATE_GROUP(errors.MappingError):
    """duplicate definition for struct group `{key}`"""


def parse_options(line_tokens):
    return parameters({
        'align': positive_integer,
        'endian': one_of('big', 'little'),
        'first': set,
        'size': positive_integer,
        'terminator': hexdump
    }, line_tokens)


def parse_struct_header(line_tokens):
    name, *flag_tokens = line_tokens # TODO: support for aliases
    options = parameters({'next': set, 'last': boolean}, flag_tokens)
    if 'last' in options:
        NEXT_LAST_CONFLICT.require('next' not in options)
        return name, set()
    if 'next' in options:
        return name, options['next']
    return name, None # no restrictions; full list filled in later.


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
        typename, name, fixed = parts_of(tnf, ':', 1, 3, False)
        member = UNRECOGNIZED_TYPE.get(types, typename)
        if fixed is None:
            NOT_FIXED_OR_NAMED.require(name is not None)
        else:
            FIXED_AND_NAMED.require(name is None)
            fixed = member.parse(fixed, name)
        self.member_data.append((member, name, fixed))


class StructGroupDescriptionLSM:
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
        self.struct_data = StructData(line_tokens, self.options.get('align', 1))


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
                self.structs, self.graph, **self.options
            )
        )
        self._reset()
