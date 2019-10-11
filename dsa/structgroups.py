from .errors import wrap as wrap_errors, SequenceError, UserError
from .parsing.line_parsing import line_parser
from .parsing.token_parsing import single_parser
from itertools import count


class UNRECOGNIZED_FOLLOWERS(UserError):
    """unrecognized followers `{extra}` for struct `{current}`"""


class CHUNK_END_CONFLICT(UserError):
    """end of chunk may be specified in at most one way (terminator sequence, `last` struct or explicit count of structs)"""


class CHUNK_LOADING_FAILED(UserError):
    """couldn't load chunk ({reason})"""


class NO_MATCH(SequenceError):
    """couldn't match a struct at chunk offset 0x{offset:X}"""


# Doesn't quite fit the pattern for a MappingError.
class INVALID_FOLLOWER(UserError):
    """struct `{name}` invalid here (valid options: {followers})"""


class BAD_CHUNK_SIZE(UserError):
    """chunk has {actual} structs; exactly {required} required"""


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
        counted = self._count is not None
        terminated = self._terminator is not None
        has_last = not all(self._graph.values())
        end_methods = int(terminated) + int(has_last) + int(counted)
        CHUNK_END_CONFLICT.require(end_methods <= 1)
        self._expect_termination = terminated or has_last


    @property
    def alignment(self):
        return self._alignment


    def _terminator_amount(self, data, loc):
        t = self._terminator
        return 0 if t is None else len(t) if data[loc:loc+len(t)] == t else 0


    def _extract(self, candidates, data, offset, chunk_label):
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


    def _parse(self, tokens, previous):
        followers = self._graph[previous]
        # Name extraction can't fail, since empty lines are skipped.
        name, tokens = _struct_name_parser(tokens)
        INVALID_FOLLOWER.require(
            name in followers, name=name, followers=followers
        )
        return name, self._structs[name].parse(tokens)


    def _parse_end(self, count):
        BAD_CHUNK_SIZE.require(
            self._count is None or count == self._count,
            actual=count,
            required=self._count
        )
        return b'' if self._terminator is None else self._terminator


    def assemble(self, lines):
        previous = None
        result = bytearray()
        for i, line in enumerate(lines, 1):
            previous, data = wrap_errors(
                f'struct #{i}', self._parse, line, previous
            )
            result.extend(data)
        result.extend(self._parse_end(len(lines)))
        return bytes(result)


    def item_size(self, name):
        try:
            return self._structs[name].size
        except: # Bad struct name? Wait until assembly to report the error.
            return 0


    def _understand_failure(self, i):
        if self._expect_termination:
            return "didn't find a valid terminator sequence or `last` chunk"
        if self._count is None:
            return "couldn't parse struct #{i}"
        return "couldn't parse struct {i}/{self._count}"


    def _progress(self, i):
        return f'{i}/{self._count}' if self._count is not None else f'#{i}'


    def _candidates(self, data, offset, previous):
        read_to_end = self._count is None and not self._expect_termination
        if offset == len(data) and read_to_end:
            # consumed the entire block without other termination; success.
            return 0, None
        amount = self._terminator_amount(data, offset)
        if amount != 0:
            # reached a valid terminator; success.
            return amount, None
        return 0, self._graph[previous]
        # if there are no candidates, reached a valid `last` struct; success.


    # Get the disassembled lines for a chunk and the corresponding chunk size.
    def disassemble(self, config, chunk_label, data, register, label_ref):
        # `config` is ignored.
        previous = None
        offset = 0
        lines = []
        enumerator = (
            range(1, self._count+1)
            if self._count is not None
            else count(1)
        )
        for i in enumerator:
            adjustment, candidates = self._candidates(data, offset, previous)
            if not candidates:
                offset += adjustment
                break
            result = self._extract(candidates, data, offset, chunk_label)
            CHUNK_LOADING_FAILED.require(
                result is not None,
                reason=self._understand_failure(i)
            )
            struct_name, match, referents, struct_size = result
            for referent in referents:
                register(*referent)
            lines.append(self._format(
                f'Struct {struct_name} ({self._progress(i)})',
                struct_name, match, label_ref
            ))
            offset += struct_size
            previous = struct_name
        assert self._count in {None, i}
        return offset, lines
