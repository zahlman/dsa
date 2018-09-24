from arguments import boolean, parameters, positive_integer, one_of
from parse_config import cached_loader, parts_of, process
from structs import Struct, StructGroup
from collections import OrderedDict


def parse_options(line_tokens):
    return parameters({
        'align': positive_integer,
        'endian': one_of('big', 'little'),
        'size': positive_integer,
        'first': set
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
    def __init__(self, line_tokens):
        self.name, self.followers = parse_struct_header(line_tokens)
        self.struct_doc = []
        self.member_data = []


    def create(self):
        return (
            self.name,
            Struct(self.member_data, self.struct_doc),
            self.followers
        )


    def add_member(self, line_tokens, doc, load_type):
        self.struct_doc.append(doc)
        tnf, *options = line_tokens
        typename, name, fixed = parts_of(tnf, ':', 1, 3, False)
        member_maker, whitelist = load_type(typename)
        member = member_maker(parameters(whitelist, options), name)
        if fixed is not None:
            fixed = member.parse(fixed)
        self.member_data.append((member, fixed))


class StructGroupDescriptionLSM:
    def __init__(self, load_type):
        self.group_doc = []
        self.structs = OrderedDict()
        self.options = None
        self.struct_data = None
        self.graph = OrderedDict()
        self.load_type = load_type


    def _push_old_struct(self):
        if self.struct_data is None:
            return
        name, struct, followers = self.struct_data.create()
        if name in self.structs:
            raise ValueError(f'duplicate struct definition for {name}')
        self.structs[name] = struct
        self.graph[name] = followers
        self.struct_data = None


    def add_line(self, position, indent, line_tokens, doc):
        if position == 0: # group-level documentation
            self.group_doc.append(doc)
            return
        if indent: # middle of a struct definition
            if self.struct_data is None:
                raise ValueError('member definition outside of struct')
            self.struct_data.add_member(line_tokens, doc, self.load_type)
            return
        if self.options is None: # header
            self.options = parse_options(line_tokens)
            return
        # Otherwise: beginning of a new struct.
        self._push_old_struct()
        self.struct_data = StructData(line_tokens)


    def result(self, name):
        if self.options is None:
            raise ValueError('empty struct group definition (no option line)')
        self._push_old_struct()
        if not self.structs:
            raise ValueError('empty struct group definition (no structs)')
        return StructGroup(
            self.structs, self.group_doc, self.graph, **self.options
        )
