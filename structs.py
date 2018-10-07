import re


class Struct:
    def __init__(self, member_data, alignment):
        pattern = bytearray()
        # The template value is "write-only"; the non-fixed bytes of the
        # bytearray will be replaced each time and are meaningless except
        # when a copy is made by `parse`.
        self.template = bytearray()
        offsets = []
        members = []
        names = []
        position = 0
        for member, name, fixed in member_data:
            size = member.size
            if fixed is None:
                offsets.append(position)
                members.append(member)
                names.append(name)
                pattern.extend(b'(' + (b'.' * size) + b')')
                self.template.extend(bytes(size))
            else:
                assert len(fixed) == size
                pattern.extend(re.escape(fixed))
                self.template.extend(fixed)
            position += size
        assert position == len(self.template)
        padding = -position % alignment
        pattern.extend(b'.' * padding)
        self.template.extend(bytes(padding))
        self.pattern = re.compile(bytes(pattern), re.DOTALL)
        self.offsets = tuple(offsets)
        self.members = tuple(members)
        self.names = tuple(names)


    def format_from(self, source, position, disassembler):
        match = self.pattern.match(source, position)
        if match is None:
            # This struct wasn't matched, but maybe another one will be.
            return None
        return tuple(
            member.format(value, disassembler, name)
            for member, name, value in zip(
                self.members, self.names, match.groups()
            )
        ), len(self.template)


    def parse(self, tokens):
        # This invariant should be upheld by the struct lookup/dispatch.
        assert len(tokens) == len(self.members)
        for member, token, offset in zip(self.members, tokens, self.offsets):
            raw = member.parse(token)
            assert len(raw) == member.size
            self.template[offset:offset+len(raw)] = raw
        return bytes(self.template)


def _normalized_graph(graph, first):
    all_nodes = set(graph.keys())
    result = {}
    for current, followers in graph.items():
        if followers is None:
            result[current] = all_nodes
            continue
        extra = followers - all_nodes
        if extra:
            raise ValueError(
                f'unrecognized followers `{extra}` for struct `{current}`'
            )
        result[current] = followers
    result[None] = all_nodes if first is None else first
    # Preserve order.
    ordering = list(graph.keys()).index
    for k, v in result.items():
        result[k] = tuple(sorted(v, key=ordering))
    return result


class StructGroup:
    def __init__(
        self, structs, graph,
        first=None, align=4, endian='little', size=None, terminator=None
    ):
        self.structs = structs # TODO: optimized dispatch
        self.alignment = align
        self.endian = endian # TODO: implement big-endian
        self.size = size
        self.terminator = terminator
        self.graph = _normalized_graph(graph, first)


    @property
    def terminator_size(self):
        return 0 if self.terminator is None else len(self.terminator)


    def check_alignment(self, position):
        if position % self.alignment != 0:
            raise ValueError(
                f'chunk not aligned to multiple of {self.alignment} boundary'
            )


    def _remaining(self, count):
        return None if self.size is None else self.size - count


    def _at_end(self, source, position):
        t = self.terminator
        if t is None:
            return False
        return t == source[position:position+len(t)]


    def _candidates(self, source, position, previous, count):
        if self._at_end(source, position):
            # N.B. If there are `last` structs in the group and we didn't
            # reach one, this is *not* considered an error.
            result = set()
        else:
            result = self.graph[previous]
            if self.terminator is not None and not result:
                raise ValueError(
                    f'missing terminator after `{previous}` struct'
                )
        # Validate against count, if applicable.
        remaining = self._remaining(count)
        if not result and (remaining not in {0, None}):
            raise ValueError(
                f'premature end of chunk; {remaining} struct(s) missing'
            )
        if result and remaining == 0:
            if self.terminator is not None:
                raise ValueError(
                    f'missing terminator after {count} struct(s)'
                )
            # Otherwise: end of counted block, and last struct was not `last`;
            # this is not an error, but we stop formatting here.
            result = set()
        return result


    def format_from(self, source, position, previous, count, disassembler):
        candidates = self._candidates(source, position, previous, count)
        if not candidates:
            return None
        for name in candidates:
            struct = self.structs[name]
            try:
                result = struct.format_from(source, position, disassembler)
            except ValueError as e:
                raise ValueError(f'Struct {name}: {e}')
            if result is not None:
                return name, result
        # There were candidates, but none worked. Maybe premature end of data?
        raise ValueError(f'invalid source data')


    def parse(self, tokens, previous=None):
        followers = self.graph[previous]
        # Name extraction can't fail, since empty lines are skipped.
        name, *tokens = tokens
        if name not in followers:
            raise ValueError(' '.join((
                f'struct `{name}` invalid or unrecognized at this point',
                f'(valid options: {followers})'
            )))
        return self.structs[name].parse(tokens)
