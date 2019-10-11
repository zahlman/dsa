from .errors import wrap as wrap_errors, UserError
import re


class Member:
    # Item in a Struct that delegates to either a Value or Pointer
    # for parsing and formatting.
    def __init__(self, implementation, name, offset):
        self._implementation = implementation # Value or Pointer
        self._name = name
        self._offset = offset # byte offset relative to the containing Struct.


    @property
    def offset(self):
        return self._offset # read-only


    @property
    def size(self):
        return self._implementation.size


    @property
    def pattern(self):
        return b'(' + (b'.' * self.size) + b')'


    @property
    def template(self):
        return bytes(self.size)


    @property
    def tag(self):
        typename = self._implementation.typename
        name = self._name
        return f'Member `{name}` (of type `{typename}`)'


    def referents(self, raw, chunk_label):
        label = f'{chunk_label} {self._name}'
        result = self._implementation.pointer_value(raw, label)
        if result is not None:
            yield result


    def format(self, value, lookup):
        return wrap_errors(
            self.tag, self._implementation.format, value, lookup
        )


    def parse(self, items):
        return wrap_errors(
            self.tag, self._implementation.parse, items
        )


def _process_member_data(member_data, alignment):
    pattern = bytearray()
    # The template value is "write-only"; the non-fixed bytes of the
    # bytearray will be replaced each time and are meaningless except
    # when a copy is made by `parse`.
    template = bytearray()
    members = []
    position = 0
    for implementation, name, fixed in member_data:
        if fixed is None:
            member = Member(implementation, name, len(template))
            members.append(member)
            pattern.extend(member.pattern)
            template.extend(member.template)
        else:
            assert len(fixed) == implementation.size
            pattern.extend(re.escape(fixed))
            template.extend(fixed)
    padding = -len(template) % alignment
    pattern.extend(b'.' * padding)
    template.extend(bytes(padding))
    return re.compile(bytes(pattern), re.DOTALL), template, tuple(members)


class Struct:
    def __init__(self, member_data, alignment):
        self._pattern, self._template, self._members = _process_member_data(
            member_data, alignment
        )


    @property
    def size(self):
        return len(self._template)


    def _match_handlers(self, match):
        return zip(self._members, match.groups())


    def extract(self, name, data, offset, chunk_label):
        match = self._pattern.match(data, offset)
        if match is None:
            return None
        referents = tuple(
            r
            for member, group in self._match_handlers(match)
            for r in member.referents(group, chunk_label)
        )
        return name, match, referents, self.size


    def format(self, match, lookup):
        return tuple(
            member.format(value, lookup)
            for member, value in self._match_handlers(match)
        )


    def parse(self, tokens):
        # This invariant should be upheld by the struct lookup/dispatch.
        assert len(tokens) == len(self._members)
        for member, token in zip(self._members, tokens):
            raw = member.parse(token)
            offset = member.offset
            assert len(raw) == member.size
            # We overwrite the same set of bytes each time, so there's
            # no chance of picking up garbage from a previous call.
            self._template[offset:offset+len(raw)] = raw
        return bytes(self._template)
