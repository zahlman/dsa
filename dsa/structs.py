from . import errors
from .parsing.line_parsing import TokenError
import re


class UNRECOGNIZED_FOLLOWERS(errors.UserError):
    """unrecognized followers `{extra}` for struct `{current}`"""


class MISALIGNED_CHUNK(errors.UserError):
    """chunk not aligned to multiple of {alignment} boundary"""


class MISSING_TERMINATOR_NATURAL(errors.UserError):
    """missing terminator after `{previous}` struct"""


class MISSING_CHUNKS(errors.UserError):
    """premature end of chunk; {remaining} struct(s) missing"""


class MISSING_TERMINATOR_COUNTED(errors.UserError):
    """missing terminator after {count} struct(s)"""


class NO_MATCH(errors.SequenceError):
    """invalid source data at 0x{position:X}"""


class CHUNK_TOO_BIG(errors.UserError):
    """too many structs in chunk"""


class CHUNK_TOO_SMALL(errors.UserError):
    """not enough structs in chunk"""


class MULTIPART_STRUCT_NAME(TokenError):
    """struct name token must be single-part (has {actual} parts)"""


# Doesn't quite fit the pattern for a MappingError.
class INVALID_FOLLOWER(errors.UserError):
    """struct `{name}` invalid here (valid options: {followers})"""


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


    @property
    def size(self):
        return len(self.template)


    def _match_handlers(self, match):
        return zip(self.members, self.names, match.groups())


    def extract(self, name, source, position):
        match = self.pattern.match(source, position)
        return None if match is None else (
            name, self, match, [
                referent
                for member, name, value in self._match_handlers(match)
                for referent in member.referents(name, value)
            ]
        )


    def format(self, match, labels):
        return tuple(
            member.format(name, value, labels)
            for member, name, value in self._match_handlers(match)
        ), self.size


    def parse(self, tokens):
        # This invariant should be upheld by the struct lookup/dispatch.
        assert len(tokens) == len(self.members)
        for member, name, token, offset in zip(
            self.members, self.names, tokens, self.offsets
        ):
            raw = member.parse(name, token)
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
        UNRECOGNIZED_FOLLOWERS.require(not extra, extra=extra, current=current)
        result[current] = followers
    result[None] = all_nodes if first is None else first
    # Preserve order.
    ordering = list(graph.keys()).index
    for k, v in result.items():
        result[k] = tuple(sorted(v, key=ordering))
    return result


class StructGroup:
    def __init__(self, structs, graph, options):
        self.structs = structs # TODO: optimized dispatch
        self.alignment = options.align
        self.endian = options.endian # TODO: implement big-endian
        self.size = options.count
        self.terminator = options.terminator
        self.graph = _normalized_graph(graph, options.first)


    @property
    def terminator_size(self):
        return 0 if self.terminator is None else len(self.terminator)


    def check_alignment(self, position):
        MISALIGNED_CHUNK.require(
            position % self.alignment == 0,
            alignment=self.alignment
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
            MISSING_TERMINATOR_NATURAL.require(
                result or (self.terminator is None),
                previous=previous
            )
        # Validate against count, if applicable.
        remaining = self._remaining(count)
        if not result:
            MISSING_CHUNKS.require(
                remaining in {0, None}, remaining=remaining
            )
        elif remaining == 0:
            MISSING_TERMINATOR_COUNTED.require(
                self.terminator is None, count=count
            )
            # Otherwise: end of counted block, and last struct was not `last`;
            # this is not an error, but we stop formatting here.
            result = set()
        return result


    def extract(self, source, position, previous, count):
        candidates = self._candidates(source, position, previous, count)
        return NO_MATCH.first_not_none((
            self.structs[name].extract(name, source, position)
            for name in candidates
        ), position = position) if candidates else None


    def format_from(self, name, struct, match, position, labels):
        return name, errors.wrap(
            f'Struct {name} (at 0x{position:X})',
            struct.format, match, labels
        )


    def parse(self, tokens, count, previous):
        CHUNK_TOO_BIG.require(self.size is None or count < self.size)
        followers = self.graph[previous]
        # Name extraction can't fail, since empty lines are skipped.
        name, *tokens = tokens
        name, = MULTIPART_STRUCT_NAME.pad(name, 1, 1)
        INVALID_FOLLOWER.require(
            name in followers, name=name, followers=followers
        )
        return name, self.structs[name].parse(tokens)


    def parse_end(self, count):
        CHUNK_TOO_SMALL.require(self.size is None or count >= self.size)
        return b'' if self.terminator is None else self.terminator


    # Methods used by the assembler to determine the expected size of a chunk
    # without doing any actual assembly.
    def struct_size(self, name):
        try:
            return self.structs[name].size
        except: # Bad struct name? Wait until assembly to report the error.
            return 0
