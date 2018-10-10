from arguments import boolean, hexdump, parameters, positive_integer, one_of
from parse_config import parts_of
from structs import Struct, StructGroup
from collections import OrderedDict


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
    if 'next' in options and 'last' in options:
        raise ValueError('`next` and `last` options are mutually exclusive')
    if 'last' in options:
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
        if fixed is None and name is None:
            raise ValueError(f'member must have either a name or a fixed value')
        if fixed is not None and name is not None:
            raise ValueError(f'member with fixed value may not be named')
        try:
            member = types[typename]
        except KeyError:
            raise ValueError(f'unrecognized type {typename}')
        if fixed is not None:
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
        if name in self.structs:
            raise ValueError(f'duplicate struct definition for {name}')
        self.structs[name] = struct
        self.graph[name] = followers
        self.struct_data = None


    def _continue_struct(self, line_tokens):
        if self.struct_data is None:
            raise ValueError('member definition outside of struct')
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
        if self.options is None:
            raise ValueError('empty struct group definition (no option line)')
        self._push_old_struct()
        if not self.structs:
            raise ValueError('empty struct group definition (no structs)')
        if label in accumulator:
            raise ValueError(f'duplicate definition for struct group `{label}`')
        accumulator[label] = StructGroup(
            self.structs, self.graph, **self.options
        )
        self._reset()
