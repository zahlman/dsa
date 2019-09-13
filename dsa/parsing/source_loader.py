from ..errors import parse_int, MappingError, UserError
from .line_parsing import integer, TokenError


class UNRECOGNIZED_LABEL(MappingError):
    """unrecognized label `@{key}`"""


class UNRECOGNIZED_DIRECTIVE(MappingError):
    """unrecognized directive `@{key}`"""


class INVALID_LABEL(TokenError):
    """invalid syntax for `@label` directive"""


class INVALID_LABEL_NAME(TokenError):
    """`@label` name must be a single-part token (has {actual} parts)"""


class INVALID_LABEL_POSITION(TokenError):
    """`@label` position must be a single-part token (has {actual} parts)"""


class MISSING_BRACE(UserError):
    """missing open brace for `@{directive}` directive"""


class UNRECOGNIZED_GROUP_NAME(MappingError):
    """unrecognized group name `{key}`"""


class GROUPNAME_SINGLE(TokenError):
    """group name must be a single, single-part token"""


class UNMATCHED_BRACE(UserError):
    """unmatched opening or closing brace"""


class BAD_LINE_START(TokenError):
    """directive or struct name must be single-part token (has {actual} parts)"""


class DIRECTIVE_INSIDE_CHUNK(UserError):
    """directives not allowed inside `@group` block"""


class JUNK_AFTER_CLOSE_BRACE(UserError):
    """closing brace must be on a line by itself"""


class NON_DIRECTIVE_OUTSIDE_CHUNK(UserError):
    """non-directive lines must be inside `@group` blocks"""


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


class Chunk:
    def __init__(self, location, filters, group):
        self.location = location
        self.filters = filters
        self.group = group
        self.lines = []
        self.size = group.terminator_size


    def add_line(self, tokens):
        self.lines.append(tokens)
        self.size += self.group.struct_size(tokens[0][0])


    def complete(self, label_lookup):
        previous = None
        result = bytearray()
        for i, line in enumerate(self.lines):
            previous, data = self.group.parse(
                _resolve_labels(line, label_lookup), i, previous
            )
            result.extend(data)
        result.extend(self.group.parse_end(len(self.lines)))
        for f in reversed(self.filters):
            pass # TODO
        return self.location, bytes(result)


class SourceAccumulator:
    def __init__(self):
        self._chunks = []
        self._chunk_open = False # whether we are in the middle of a chunk.
        self._labels = {}
        self._last_position = None


    @property
    def closed(self):
        return not self._chunk_open


    def add_line(self, tokens):
        assert self._chunks and not self.closed # should be maintained outside
        self._chunks[-1].add_line(tokens)


    def add_label(self, name, position):
        self._last_position = position
        self._labels[name] = position


    def start_chunk(self, filters, group):
        assert self.closed # should have been caught earlier.
        self._chunks.append(Chunk(self._last_position, filters, group))
        self._chunk_open = True


    def finish_chunk(self):
        assert self._chunks and not self.closed # should be maintained outside
        # Estimate position after the chunk.
        # This will *normally* give the correct value, but some
        # filters could conceivably mess it up.
        if self._last_position is not None:
            self._last_position += self._chunks[-1].size
        self._chunk_open = False


    def resolve(self):
        UNMATCHED_BRACE.require(self.closed)
        result = {}
        for chunk in self._chunks:
            key, value = chunk.complete(self._labels)
            DUPLICATE_CHUNK_LOCATION.add_unique(result, key, value)
        return result


class SourceLoader:
    def __init__(self, structgroups):
        self.filter_stack = []
        self.labels = {}
        self.all_groups = structgroups


    def _dispatch(self, accumulator, first, rest):
        UNRECOGNIZED_DIRECTIVE.get(
            {
                'label': self._process_label,
                'filter': self._process_filter,
                'group': self._process_group
            },
            first
        )(accumulator, rest)


    def _process_label(self, accumulator, tokens):
        name, position = INVALID_LABEL.pad(tokens, 1, 2)
        accumulator.add_label(
            INVALID_LABEL_NAME.singleton(name),
            INVALID_LABEL_POSITION.convert(UserError, integer, position)
        )


    def _verify_brace(self, tokens, dname):
        MISSING_BRACE.require(bool(tokens), directive=dname)
        *args, brace = tokens
        MISSING_BRACE.require(brace == ['{'], directive=dname)
        return args


    def _process_filter(self, accumulator, tokens):
        # TODO actually create some kind of Filter object.
        self.filter_stack.append(self._verify_brace(tokens, 'filter'))


    def _process_group(self, accumulator, tokens):
        tokens = self._verify_brace(tokens, 'group')
        tokens = GROUPNAME_SINGLE.singleton(tokens) # single token...
        tokens = GROUPNAME_SINGLE.singleton(tokens) # with a single part
        accumulator.start_chunk(
            self.filter_stack.copy(),
            UNRECOGNIZED_GROUP_NAME.get(self.all_groups, tokens)
        )


    def _close_directive(self, accumulator):
        if accumulator.closed:
            # then the brace must be closing a filter.
            UNMATCHED_BRACE.convert(IndexError, self.filter_stack.pop)
        else:
            accumulator.finish_chunk()


    def __call__(self, accumulator, indent, tokens):
        # Indentation is irrelevant.
        assert tokens # empty lines were preprocessed out.
        first, *rest = tokens
        # FIXME: relax this restriction if/when implicit struct names
        # are implemented for single-struct groups.
        first = BAD_LINE_START.singleton(first)
        if first.startswith('@'):
            DIRECTIVE_INSIDE_CHUNK.require(accumulator.closed)
            self._dispatch(accumulator, first[1:], rest)
        elif first == '}':
            JUNK_AFTER_CLOSE_BRACE.require(not rest)
            self._close_directive(accumulator)
        else:
            NON_DIRECTIVE_OUTSIDE_CHUNK.require(not accumulator.closed)
            accumulator.add_line(tokens)
    
    
def make_sourceloader(structgroups):
    return SourceLoader(structgroups), SourceAccumulator()
