from arguments import parameters
from parse_config import parts_of
import member_template
import re


def instantiate_member(line_tokens):
    tnf, *options = line_tokens
    typename, name, fixed = parts_of(tnf, ':', 1, 3, False)
    filename = f'{typename}.txt' # For now.
    member_maker, whitelist = member_template.load(filename)
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
    def __init__(self, member_data, doc):
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
        self.doc = doc # Unused for now.


    def format_from(self, source, position):
        match = self.pattern.match(source, position)
        if match is None:
            # This struct wasn't matched, but maybe another one will be.
            return None
        return tuple(
            member.format(value)
            for member, value in zip(self.members, match.groups())
        )


    def parse(self, tokens):
        # This invariant should be upheld by the struct lookup/dispatch.
        assert len(tokens) == len(self.members)
        for member, token, offset in zip(self.members, tokens, self.offsets):
            raw = member.parse(token)
            assert len(raw) == member.size
            self.template[offset:offset+len(raw)] = raw
        return bytes(self.template)
