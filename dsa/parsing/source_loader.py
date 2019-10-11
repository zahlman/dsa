from ..errors import MappingError, UserError
from ..ui.tracing import trace
from .line_parsing import line_parser
from .token_parsing import single_parser


class UNRECOGNIZED_LABEL(MappingError):
    """unrecognized label `@{key}`"""


class UNNAMED_GROUP(UserError):
    """{name} chunk must be empty, since no chunk format is named"""


class LABEL_PARAMS(UserError):
    """chunk-internal label may not have parameters"""


class UNCLOSED_CHUNK(UserError):
    """missing `@@` line to close chunk before starting a new one"""


class STRUCT_OUTSIDE_CHUNK(UserError):
    """struct must be inside a chunk"""


class NO_CHUNK_DEFINITION(UserError):
    """chunk has no group/chunk name line"""


class UNSUPPORTED_GROUP(UserError):
    """`{name}` group is unsupported"""


class TOO_MANY_ATS(UserError):
    """unrecognized directive; may have at most two @ signs"""


class DUPLICATE_CHUNK_LOCATION(MappingError):
    """duplicate definition for chunk at 0x{key:X}"""


def _resolve_labels_sub(subtoken, label_lookup):
    if not subtoken.startswith('@'):
        return subtoken
    label = subtoken[1:]
    return str(UNRECOGNIZED_LABEL.get(label_lookup, label))
    # It will get converted back to int later. FIXME this parsing is hax


def _resolve_labels(line, label_lookup):
    return [
        [
            _resolve_labels_sub(subtoken, label_lookup)
            for subtoken in token
        ]
        for token in line
    ]


class _DummyGroup:
    """A fake group that works only if the chunk is empty, producing b''."""
    def __init__(self, name):
        self._name = name


    def assemble(self, lines):
        UNNAMED_GROUP.require(not lines, name=self._name)
        return b''


    def item_size(self, name):
        raise UNNAMED_GROUP(name=self._name)


_chunk_header_parser = line_parser(
    'chunk info',
    single_parser('name', 'string'),
    single_parser('position', 'integer'),
    required=2
)


class Chunk:
    def __init__(self):
        self._location = None
        self._filters = [] # (name, tokens) filter specs.
        self._group = None
        self._chunk_name = None
        self._lines = []
        self._labels = [] # (name, position) assuming unfiltered.
        # TODO: ensure filters won't corrupt label info.
        self._offset = 0


    @property
    def labels(self):
        return self._chunk_name, self._location, tuple(self._labels)


    def _add_filter_or_label(self, first, rest):
        if self._group is None:
            # Before the group identifier, single-@ lines are for filters.
            self._filters.append((first, rest))
        else:
            # Afterward, they're group-internal labels.
            LABEL_PARAMS.require(not params)
            self._labels.append((name, self._location + self._offset))


    def _set_group(self, group, params):
        UNCLOSED_CHUNK.require(self._group is None)
        self._group = group
        self._chunk_name, self._location = _chunk_header_parser(params)


    def _add_struct(self, first, rest):
        STRUCT_OUTSIDE_CHUNK.require(self._group is not None)
        self._lines.append(((first,), *rest))
        self._offset += self._group.item_size(first)


    def add_line(self, group_lookup, ats, first, rest):
        # Return whether this is the last line of a group.
        if ats == 2:
            if not first and not rest: # terminator.
                NO_CHUNK_DEFINITION.require(self._group is not None)
                return True
            group = group_lookup.get(first, None)
            if group is None:
                group = _DummyGroup(first)
                if first:
                    trace(f'Warning: unrecognized group name `{first}`.')
                    trace('This will cause an error later if the group is not empty.')
            self._set_group(group, rest)
        elif ats == 1:
            self._add_filter_or_label(first, rest)
        elif ats == 0:
            self._add_struct(first, rest)
        else:
            raise TOO_MANY_ATS
        return False


    def complete(self, pack_all, label_lookup):
        lines = [_resolve_labels(line, label_lookup) for line in self._lines]
        return self._location, pack_all(
            self._group.assemble(lines), self._filters
        )


def _process_ats(tokens):
    assert tokens # empty lines were preprocessed out.
    first, *rest = tokens
    # TODO: revisit this if/when implicit struct names
    # are implemented for single-struct groups.
    first = single_parser('directive or struct name', 'string')(first)
    size = len(first)
    first = first.lstrip('@')
    count = size - len(first)
    return count, first, rest


class SourceLoader:
    def __init__(self, structgroups, filter_library):
        self._chunks = []
        self._current = None # either None or the last of the self._chunks.
        self._group_lookup = structgroups
        self._pack_all = filter_library.pack_all


    def _get_labels(self):
        labels = {}
        for chunk in self._chunks:
            name, location, internal = chunk.labels
            # TODO: process internal labels.
            labels[name] = location
        return labels


    def line(self, indent, tokens):
        # Indentation is irrelevant.
        count, first, rest = _process_ats(tokens)
        if self._current is None:
            self._current = Chunk()
            self._chunks.append(self._current)
        if self._current.add_line(self._group_lookup, count, first, rest):
            self._current = None


    def result(self):
        processed = {}
        label_lookup = self._get_labels()
        for chunk in self._chunks:
            key, value = chunk.complete(self._pack_all, label_lookup)
            DUPLICATE_CHUNK_LOCATION.add_unique(processed, key, value)
        return processed
