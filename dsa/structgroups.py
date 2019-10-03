from .errors import wrap as wrap_errors, SequenceError, UserError
from .parsing.line_parsing import line_parser
from .parsing.token_parsing import single_parser
from itertools import count


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
    """couldn't match a struct at chunk offset 0x{offset:X}"""


class CHUNK_TOO_BIG(UserError):
    """too many structs in chunk"""


# Doesn't quite fit the pattern for a MappingError.
class INVALID_FOLLOWER(UserError):
    """struct `{name}` invalid here (valid options: {followers})"""


class CHUNK_TOO_SMALL(UserError):
    """not enough structs in chunk"""


_struct_name_parser = line_parser(
    'struct', single_parser('name', 'string'), required=1, more=True
)


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


    def _at_end(self, get, offset):
        t = self.terminator
        if t is None:
            return False
        return t == get(offset, len(t))


    def _candidates(self, get, offset, previous, count):
        if self._at_end(get, offset):
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


    def extract(self, get, offset, previous, count):
        candidates = self._candidates(get, offset, previous, count)
        if not candidates:
            return None
        # name, match, referents, size
        # referents is a list of (group name, location, label_base) tuples
        return NO_MATCH.first_not_none((
            self.structs[name].extract(name, get, offset)
            for name in candidates
        ), offset=offset)


    def format(self, tag, name, match, lookup):
        # At least for Python 3.6, the outer parentheses are necessary.
        return ((name,), *wrap_errors(
            tag, self.structs[name].format, match, lookup
        ))


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


    # Get the disassembled lines for a chunk and the corresponding chunk size.
    def load(self, get, register, label_ref):
        struct_name = None
        offset = 0
        lines = []
        for i in count():
            result = self.extract(get, offset, struct_name, i)
            if result is None:
                return offset + self.terminator_size, lines
            struct_name, match, referents, size = result
            offset += size
            for referent in referents:
                register(*referent)
            lines.append(self.format(
                f'Struct {struct_name} (at 0x{offset:X})',
                struct_name, match, label_ref
            ))
