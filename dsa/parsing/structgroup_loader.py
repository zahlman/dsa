from ..errors import MappingError, UserError
from ..structs import Struct, StructGroup
from .file_parsing import SimpleLoader
from .line_parsing import argument_parser, TokenError
from .token_parsing import single_parser
from collections import OrderedDict


class NEXT_LAST_CONFLICT(UserError):
    """`next` and `last` options are mutually exclusive"""


class BAD_MEMBER(TokenError):
    """not enough or too many tokens for member specification"""


class INVALID_TF(TokenError):
    # Should be impossible?
    """invalid typename/fixed data"""


class BAD_REFERENT(TokenError):
    """invalid specification for pointer referent"""


class UNRECOGNIZED_TYPE(MappingError):
    """unrecognized type {key}"""


class NOT_FIXED_OR_NAMED(TokenError):
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


_parse_options = argument_parser(
    {'align': 1, 'first': None, 'count': None, 'terminator': None},
    align='positive', endian={'big', 'little'},
    first='{string', count='positive', terminator='hexdump'
)


_parse_struct_options = argument_parser(
    {'next': None, 'last': False},
    next='{string', last={'true': True, 'false': False, None: True}
)


def _parse_struct_header(line_tokens):
    name, *flag_tokens = line_tokens # TODO: support for aliases
    name = single_parser('struct name', 'string')(name)
    options = _parse_struct_options(flag_tokens)
    if options.last:
        NEXT_LAST_CONFLICT.require(options.next is None)
        return name, set()
    # If nothing is specified, the None value is passed through and will be
    # replaced later with a set of all possibilities.
    return name, options.next


class StructData:
    def __init__(self, line_tokens, alignment):
        self._name, self._followers = _parse_struct_header(line_tokens)
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
            name = single_parser('member name', 'string')(name)
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
            self._options = _parse_options(tokens)
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
