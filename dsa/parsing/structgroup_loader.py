from ..errors import MappingError, UserError
from ..structs import Struct, StructGroup
from .file_parsing import SimpleLoader
from .line_parsing import argument_parser, line_parser
from .token_parsing import make_parser, single_parser
from collections import OrderedDict


class NEXT_LAST_CONFLICT(UserError):
    """`next` and `last` options are mutually exclusive"""


class BAD_MEMBER(UserError):
    """not enough or too many tokens for member specification"""


class DUPLICATE_STRUCT(MappingError):
    """duplicate struct definition for {key}"""


class MEMBER_OUTSIDE_STRUCT(UserError):
    """member definition outside of struct"""


class NO_OPTIONS(UserError):
    """empty struct group definition (no option line)"""


class NO_STRUCTS(UserError):
    """empty struct group definition (no structs)"""


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


_parse_referent = argument_parser({'referent': None}, referent='string')


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
        (member, fixed), tokens = line_parser(
            'struct member',
            make_parser(
                'typename/fixed data',
                (types, 'typename'),
                ('[string', 'fixed value')
            ),
            required=1, more=True
        )(tokens)
        if fixed:
            BAD_MEMBER.require(not tokens)
            self._data.append((member, None, member.parse(fixed), None))
        else:
            name, tokens = line_parser(
                'struct member (without fixed value)',
                single_parser('member name', 'string'),
                extracted=1, required=1, more=True
            )(tokens)
            self._data.append(
                (member, name, None, _parse_referent(tokens).referent)
            )


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
