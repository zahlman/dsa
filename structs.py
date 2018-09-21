import re


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
