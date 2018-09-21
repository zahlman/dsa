from arguments import boolean, parameters, positive_integer, one_of
import member_template
from parse_config import parts_of, process

from collections import OrderedDict
from functools import lru_cache
from os.path import basename, splitext
import re


def instantiate_member(line_tokens):
    tnf, *options = line_tokens
    typename, name, fixed = parts_of(tnf, ':', 1, 3, False)
    member_maker, whitelist = member_template.load(typename)
    member = member_maker(parameters(whitelist, options), name)
    if fixed is not None:
        fixed = member.parse(fixed)
    return member, fixed


def _regex_component(size, fixed):
    return b'(' + (b'.' * size) + b')' if fixed is None else re.escape(fixed)


def _struct_regex(member_data):
    return re.compile(b''.join(
        _regex_component(member.size, fixed)
        for member, fixed in member_data
    ))


def _template_component(size, fixed):
    return bytes(size) if fixed is None else fixed


def _struct_template(member_data):
    return bytearray(b''.join(
        _template_component(member.size, fixed)
        for member, fixed in member_data
    ))


def _struct_offsets(member_data):
    # Indicates where each parsed member goes in the parsed struct.
    position = 0
    for member, fixed in member_data:
        if fixed is None:
            yield position
        position += member.size


class Struct:
    def __init__(self, member_data, followers, doc):
        assert all(
            (fixed is None) or (len(fixed) == member.size)
            for member, fixed in member_data
        )
        self.pattern = _struct_regex(member_data)
        self.members = [
            member for member, fixed in member_data
            if fixed is None
        ]
        # The template value is "write-only"; the non-fixed bytes of the
        # bytearray will be replaced each time and are meaningless except
        # when a copy is made by `parse`.
        self.template = _struct_template(member_data)
        self.offsets = tuple(_struct_offsets(member_data))
        # Either `None` or a set of string names of other Structs.
        self._followers = followers
        self.doc = doc # Unused for now.


    def format_from(self, source, position):
        match = self.pattern.match(source, position)
        if match is None:
            # This struct wasn't matched, but maybe another one will be.
            return None
        return tuple(
            member.format(value)
            for member, value in zip(self.members, match.groups())
        ), len(self.template), self._followers


    def parse(self, tokens):
        # This invariant should be upheld by the struct lookup/dispatch.
        assert len(tokens) == len(self.members)
        for member, token, offset in zip(self.members, tokens, self.offsets):
            raw = member.parse(token)
            assert len(raw) == member.size
            self.template[offset:offset+len(raw)] = raw
        return bytes(self.template), self._followers


class StructGroup:
    def __init__(self, structs, doc, align=4, endian='little', size=None):
        self.structs = structs # OrderedDict. TODO: optimized dispatch
        self.align = align
        self.endian = endian # TODO: implement big-endian
        self.size = size
        self.doc = doc # Unused for now.


    def format_from(self, candidates, source, position):
        for name in candidates:
            struct = self.structs[name]
            result = struct.format_from(source, position)
            if result is not None:
                tokens, size, followers = result
                return ' '.join((name,) + tokens), size, followers
        raise ValueError(f'incorrectly formatted data at {position:X}')


    @property
    def all_structs(self):
        return set(self.structs.keys())


    def format_chunk(self, source, position):
        candidates = self.all_structs
        count = -1 if self.size is None else self.size
        while count != 0 and position < len(source) and candidates:
            result, size, candidates = self.format_from(
                candidates, source, position
            )
            if candidates is None: # no candidates -> empty set.
                candidates = self.all_structs
            assert candidates <= self.all_structs
            position += size
            yield result
            count -= 1
        if count > 0:
            raise ValueError(
                f'premature end of chunk; {count} struct(s) missing'
            )
        if candidates and count < 0:
            # when count == 0, we may not have reached a terminator, but that's
            # explicitly OK since the point is that the count determines the
            # chunk boundary.
            assert position == len(source)
            raise ValueError(
                "premature end of data; didn't reach terminator struct"
            )


    def parse(self, tokens, followers):
        # Name extraction can't fail, since empty lines are skipped.
        name, *tokens = tokens
        if name not in followers:
            raise ValueError(' '.join((
                f'struct `{name}` invalid or unrecognized at this point',
                f'(valid options: {followers})'
            )))
        # `followers` should be a subset of struct keys.
        return self.structs[name].parse(tokens)


def parse_options(line_tokens):
    return parameters({
        'align': positive_integer,
        'endian': one_of('big', 'little'),
        'size': positive_integer
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


def make_struct_group(name, lines):
    group_doc = []
    structs = OrderedDict()
    options = None
    name = None
    struct_doc = []
    followers = None
    member_data = []
    for position, indent, line_tokens, doc in process(lines):
        if position == 0:
            group_doc.append(doc)
        elif indent: # middle of a struct definition.
            struct_doc.append(doc)
            member_data.append(instantiate_member(line_tokens))
        elif options is None: # header
            options = parse_options(line_tokens)
        # If we get here: beginning of a new struct.
        else:
            if name is not None: # clean up the old one first 
                structs[name] = Struct(member_data, followers, struct_doc)
                member_data = []
                struct_doc = []
            name, followers = parse_struct_header(line_tokens)
            if name in structs:
                raise ValueError(f'duplicate struct definition for {name}')
    # Finish up last struct and make the group.
    if options is None:
        raise ValueError('empty struct group definition (no option line)')
    if name is None:
        raise ValueError('empty struct group definition (no structs)')
    structs[name] = Struct(member_data, followers, struct_doc)
    return StructGroup(structs, group_doc, **options)


@lru_cache(None)
def load(filename):
    name = splitext(basename(filename))[0]
    with open(filename) as f:
        return make_struct_group(name, f)
