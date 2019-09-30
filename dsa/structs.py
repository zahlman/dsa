from .errors import wrap as wrap_errors, SequenceError, UserError
from .parsing.line_parsing import line_parser
from .parsing.token_parsing import single_parser
import re


class UNRECOGNIZED_FOLLOWERS(UserError):
    """unrecognized followers `{extra}` for struct `{current}`"""


class MISALIGNED_CHUNK(UserError):
    """chunk not aligned to multiple of {alignment} boundary"""


class MISSING_TERMINATOR_NATURAL(UserError):
    """missing terminator after `{previous}` struct"""


class MISSING_CHUNKS(UserError):
    """premature end of chunk; {remaining} struct(s) missing"""


class MISSING_TERMINATOR_COUNTED(UserError):
    """missing terminator after {count} struct(s)"""


class NO_MATCH(SequenceError):
    """invalid source data at 0x{position:X}"""


class CHUNK_TOO_BIG(UserError):
    """too many structs in chunk"""


class CHUNK_TOO_SMALL(UserError):
    """not enough structs in chunk"""


# Doesn't quite fit the pattern for a MappingError.
class INVALID_FOLLOWER(UserError):
    """struct `{name}` invalid here (valid options: {followers})"""


class Member:
    # Item in a Struct that delegates to either a Value or Pointer
    # for parsing and formatting.
    def __init__(self, implementation, name, ref_name, offset):
        self._implementation = implementation # Value or Pointer
        self._name = name
        self._ref_name = ref_name # name of group at the pointed-at location.
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


    def referent(self, source, position):
        start = position + self._offset
        raw = source[start:start+self._implementation.size]
        target = self._implementation.pointer_value(raw)
        if target is None:
            return None # _implementation was a Value.
        # Assumed to point at something even if that something isn't named.
        return self._ref_name, target, self._name


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
    for implementation, name, fixed, ref_name in member_data:
        if fixed is None:
            member = Member(implementation, name, ref_name, len(template))
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


    def _referents(self, source, position):
        for member in self._members:
            candidate = member.referent(source, position)
            if candidate is not None:
                yield candidate


    def extract(self, name, source, position):
        match = self._pattern.match(source, position)
        if match is None:
            return None
        return name, match, tuple(self._referents(source, position)), self.size


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
            self._template[offset:offset+len(raw)] = raw
        return bytes(self._template)


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


_struct_name_parser = line_parser(
    'struct', single_parser('name', 'string'), required=1, more=True
)


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
        if not candidates:
            return None
        # name, match, referents, size
        # referents is a list of (group name, location, label_base) tuples
        return NO_MATCH.first_not_none((
            self.structs[name].extract(name, source, position)
            for name in candidates
        ), position = position)


    def format(self, tag, name, match, lookup):
        tokens = wrap_errors(
            tag, self.structs[name].format, match, lookup
        )
        return (name,) + tokens


    def parse(self, tokens, count, previous):
        CHUNK_TOO_BIG.require(self.size is None or count < self.size)
        followers = self.graph[previous]
        # Name extraction can't fail, since empty lines are skipped.
        name, tokens = _struct_name_parser(tokens)
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
