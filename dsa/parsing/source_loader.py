from ..errors import MappingError, UserError
from ..ui.tracing import trace
from .line_parsing import integer, TokenError


class UNRECOGNIZED_LABEL(MappingError):
    """unrecognized label `@{key}`"""


class LABEL_PARAMS(TokenError):
    """chunk-internal label may not have parameters"""


class UNCLOSED_CHUNK(TokenError):
    """missing `@@` line to close chunk before starting a new one"""


class BAD_GROUP_LINE(TokenError):
    """bad group line; should be @@<group name> <chunk name> <position>"""


class BAD_CHUNK_NAME(TokenError):
    """chunk name must be single-part token (has {actual} parts)"""


class STRUCT_OUTSIDE_CHUNK(TokenError):
    """struct must be inside a chunk"""


class NO_CHUNK_DEFINITION(TokenError):
    """chunk has no group/chunk name line"""


class UNSUPPORTED_GROUP(TokenError):
    """`{name}` group is unsupported"""


class TOO_MANY_ATS(TokenError):
    """unrecognized directive; may have at most two @ signs"""


class BAD_LINE_START(TokenError):
    """directive or struct name must be single-part token (has {actual} parts)"""


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


    def parse(self, tokens, count, previous):
        raise UNSUPPORTED_GROUP(name=self._name)


    def parse_end(self, count):
        assert count == 0 # otherwise parse() should already have raised.
        return b''


class Chunk:
    def __init__(self):
        self._location = None
        self._filters = []
        self._group = None
        self._chunk_name = None
        self._lines = []
        self._labels = [] # (name, position) assuming unfiltered.
        # TODO: ensure filters won't corrupt label info.
        self._offset = 0


    @property
    def labels(self):
        return self._chunk_name, self._location, tuple(self._labels)


    def _add_filter_or_label(self, make_filter, first, rest):
        if self._group is None:
            # Before the group identifier, single-@ lines are for filters.
            # TODO: create an actual Filter object.
            self._filters.append(make_filter(first, rest))
        else:
            # Afterward, they're group-internal labels.
            LABEL_PARAMS.require(not params)
            self._labels.append((name, self._location + self._offset))


    def _set_group(self, group, params):
        UNCLOSED_CHUNK.require(self._group is None)
        self._group = group
        name, location = BAD_GROUP_LINE.pad(params, 2, 2)
        self._chunk_name = BAD_CHUNK_NAME.singleton(name)
        self._location = integer(location)


    def _add_struct(self, first, rest):
        STRUCT_OUTSIDE_CHUNK.require(self._group is not None)
        self._lines.append(((first,), *rest))
        self._offset += self._group.struct_size(first)


    def add_line(self, group_lookup, make_filter, ats, first, rest):
        # Return whether this is the last line of a group.
        if ats == 2:
            if not first:
                NO_CHUNK_DEFINITION.require(self._group is not None)
                return True
            group = group_lookup.get(first, None)
            if group is None:
                trace(f"Warning: unrecognized group name {first}. This will cause an error later if the group is not empty.")
                group = _DummyGroup(first)
            self._set_group(group, rest)
        elif ats == 1:
            self._add_filter_or_label(make_filter, first, rest)
        elif ats == 0:
            self._add_struct(first, rest)
        else:
            raise TOO_MANY_ATS
        return False


    def complete(self, label_lookup):
        previous = None
        result = bytearray()
        for i, line in enumerate(self._lines):
            previous, data = self._group.parse(
                _resolve_labels(line, label_lookup), i, previous
            )
            result.extend(data)
        result.extend(self._group.parse_end(len(self._lines)))
        for f in reversed(self._filters):
            pass # TODO: apply the filters.
        return self._location, bytes(result)


def _process_ats(tokens):
    assert tokens # empty lines were preprocessed out.
    first, *rest = tokens
    # TODO: revisit this if/when implicit struct names
    # are implemented for single-struct groups.
    first = BAD_LINE_START.singleton(first)
    size = len(first)
    first = first.lstrip('@')
    count = size - len(first)
    return count, first, rest


class SourceLoader:
    def __init__(self, structgroups, make_filter):
        self._chunks = []
        self._current = None # either None or the last of the self._chunks.
        self._group_lookup = structgroups
        self._make_filter = make_filter


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
        if self._current.add_line(
            self._group_lookup, self._make_filter,
            count, first, rest
        ):
            self._current = None


    def result(self):
        processed = {}
        label_lookup = self._get_labels()
        for chunk in self._chunks:
            key, value = chunk.complete(label_lookup)
            DUPLICATE_CHUNK_LOCATION.add_unique(processed, key, value)
        return processed
