import re


def _struct_info(member_data, alignment):
    pattern = bytearray()
    # The template value is "write-only"; the non-fixed bytes of the
    # bytearray will be replaced each time and are meaningless except
    # when a copy is made by `parse`.
    template = bytearray()
    offsets = []
    members = []
    position = 0
    for member, fixed in member_data:
        size = member.size
        if fixed is None:
            offsets.append(position)
            members.append(member)
            pattern.extend(b'(' + (b'.' * size) + b')')
            template.extend(bytes(size))
        else:
            assert len(fixed) == size
            pattern.extend(re.escape(fixed))
            template.extend(fixed)
        position += size
    assert position == len(template)
    padding = -position % alignment
    pattern.extend(b'.' * padding)
    template.extend(bytes(padding))
    return (
        re.compile(bytes(pattern), re.DOTALL), template,
        tuple(offsets), tuple(members)
    )

    
class Struct:
    def __init__(self, member_data, alignment, doc):
        self.pattern, self.template, self.offsets, self.members = _struct_info(
            member_data, alignment
        )
        self.doc = doc # Unused for now.


    def format_from(self, source, position, disassembler):
        match = self.pattern.match(source, position)
        if match is None:
            # This struct wasn't matched, but maybe another one will be.
            return None
        return tuple(
            member.format(value, disassembler)
            for member, value in zip(self.members, match.groups())
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
        self, structs, doc, graph,
        first=None, align=4, endian='little', size=None
    ):
        self.structs = structs # TODO: optimized dispatch
        self.alignment = align
        self.endian = endian # TODO: implement big-endian
        self.size = size
        self.doc = doc # Unused for now.
        self.graph = _normalized_graph(graph, first)


    def check_alignment(self, position):
        if position % self.alignment != 0:
            raise ValueError(
                f'chunk not aligned to multiple of {self.alignment} boundary'
            )


    def format_from(self, source, position, previous, count, disassembler):
        if count == self.size:
            # We may not have reached a terminator, but that's OK.
            return None # reached end
        candidates = self.graph[previous]
        if not candidates:
            # If this block is counted, ensure count was made up.
            if self.size is None:
                return None
            missing = self.size - count
            raise ValueError(
                f'premature end of chunk; {missing} struct(s) missing'
            )
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
