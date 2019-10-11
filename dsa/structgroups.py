from .errors import wrap as wrap_errors, SequenceError, UserError
from .parsing.line_parsing import line_parser
from .parsing.token_parsing import single_parser
from itertools import count


class UNRECOGNIZED_FOLLOWERS(UserError):
    """unrecognized followers `{extra}` for struct `{current}`"""


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
        self._structs = structs # TODO: optimized dispatch
        self._alignment = options.align
        self._count = options.count # number of structs, if exact count required
        self._terminator = options.terminator
        self._graph = _normalized_graph(graph, options.first)
        self._implicit_end = (
            self._count is None and
            self._terminator is None and
            all(self._graph.values()) # no last-in-chunk structs
        )


    @property
    def alignment(self):
        return self._alignment


    def _at_end(self, data, offset):
        t = self._terminator
        return False if t is None else (t == data[offset:offset+len(t)])


    def _candidates(self, data, offset, previous, count):
        unterminated = self._terminator is None
        if self._at_end(data, offset):
            # N.B. If there are `last` structs in the group and we didn't
            # reach one, this is *not* considered an error.
            result = set()
        else:
            result = self._graph[previous]
            MISSING_TERMINATOR_NATURAL.require(
                bool(result) or unterminated, previous=previous
            )
        # Validate against count, if applicable.
        remaining = None if self._count is None else self._count - count
        if not result:
            MISSING_CHUNKS.require(
                remaining in {0, None}, remaining=remaining
            )
        elif remaining == 0:
            MISSING_TERMINATOR_COUNTED.require(unterminated, count=count)
            # Otherwise: end of counted block, and last struct was not `last`;
            # this is not an error, but we stop formatting here.
            result = set()
        return result


    def _extract(self, data, offset, previous, count, chunk_label):
        if self._implicit_end and len(data) <= offset:
            return None # implicitly ended at end of data.
        candidates = self._candidates(data, offset, previous, count)
        if not candidates:
            return None
        # name, match, referents, size
        # referents is a list of (group name, location, label_base) tuples
        return NO_MATCH.first_not_none((
            self._structs[name].extract(name, data, offset, chunk_label)
            for name in candidates
        ), offset=offset)


    def _format(self, tag, name, match, lookup):
        # At least for Python 3.6, the outer parentheses are necessary.
        return ((name,), *wrap_errors(
            tag, self._structs[name].format, match, lookup
        ))


    def _parse(self, tokens, count, previous):
        CHUNK_TOO_BIG.require(self._count is None or count < self._count)
        followers = self._graph[previous]
        # Name extraction can't fail, since empty lines are skipped.
        name, tokens = _struct_name_parser(tokens)
        INVALID_FOLLOWER.require(
            name in followers, name=name, followers=followers
        )
        return name, self._structs[name].parse(tokens)


    def _parse_end(self, count):
        CHUNK_TOO_SMALL.require(self._count is None or count >= self._count)
        return b'' if self._terminator is None else self._terminator


    def assemble(self, lines):
        previous = None
        result = bytearray()
        for i, line in enumerate(lines):
            previous, data = self._parse(line, i, previous)
            result.extend(data)
        result.extend(self._parse_end(len(lines)))
        return bytes(result)


    def item_size(self, name):
        try:
            return self._structs[name].size
        except: # Bad struct name? Wait until assembly to report the error.
            return 0


    # Get the disassembled lines for a chunk and the corresponding chunk size.
    def disassemble(self, config, chunk_label, data, register, label_ref):
        # TODO use `config` to pass in a struct count if applicable.
        struct_name = None
        offset = 0
        lines = []
        for i in count():
            result = self._extract(data, offset, struct_name, i, chunk_label)
            if result is None:
                total_size = offset
                if self._terminator is not None:
                    total_size += len(self._terminator)
                return total_size, lines
            struct_name, match, referents, struct_size = result
            offset += struct_size
            for referent in referents:
                register(*referent)
            lines.append(self._format(
                f'Struct {struct_name} (at 0x{offset:X})',
                struct_name, match, label_ref
            ))
