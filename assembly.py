import errors
from line_parsing import TokenError


class UNRECOGNIZED_LABEL(errors.MappingError):
    """unrecognized label `@{key}`"""


class UNRECOGNIZED_DIRECTIVE(errors.MappingError):
    """unrecognized directive `@{key}`"""


class INVALID_LABEL(TokenError):
    """invalid syntax for `@label` directive"""


class INVALID_LABEL_NAME(TokenError):
    """`@label` name must be a single-part token (has {actual} parts)"""


class INVALID_LABEL_POSITION(TokenError):
    """`@label` position must be a single-part token (has {actual} parts)"""


class MISSING_BRACE(errors.UserError):
    """missing open brace for `@{directive}` directive"""


class UNRECOGNIZED_GROUP_NAME(errors.MappingError):
    """unrecognized group name `{key}`"""


class GROUPNAME_SINGLE(TokenError):
    """group name must be a single, single-part token"""


class UNMATCHED_BRACE(errors.UserError):
    """unmatched closing brace"""


class BAD_LINE_START(TokenError):
    """directive or struct name must be single-part token (has {actual} parts)"""


class DIRECTIVE_INSIDE_CHUNK(errors.UserError):
    """directives not allowed inside `@group` block"""


class JUNK_AFTER_CLOSE_BRACE(errors.UserError):
    """closing brace must be on a line by itself"""


class NON_DIRECTIVE_OUTSIDE_CHUNK(errors.UserError):
    """non-directive lines must be inside `@group` blocks"""


class DUPLICATE_CHUNK_LOCATION(errors.MappingError):
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


class SourceLoader:
    def __init__(self, structgroups):
        self.filter_stack = []
        self.labels = {}
        self.chunks = []
        self.position = 0
        self.all_groups = structgroups
        self.current_chunk = None


    def _dispatch(self, first, rest):
        UNRECOGNIZED_DIRECTIVE.get(
            {
                'label': self._process_label,
                'filter': self._process_filter,
                'group': self._process_group
            },
            first
        )(rest)


    def _process_label(self, tokens):
        name, position = INVALID_LABEL.pad(tokens, 1, 2)
        name, = INVALID_LABEL_NAME.pad(name, 1, 1)
        if position is not None:
            position, = INVALID_LABEL_POSITION.pad(position, 1, 1)
            self.position = errors.parse_int(position)
        self.labels[name] = self.position


    def _verify_brace(self, tokens, dname):
        MISSING_BRACE.require(bool(tokens), directive=dname)
        *args, brace = tokens
        MISSING_BRACE.require(brace == ['{'], directive=dname)
        return args


    def _process_filter(self, tokens):
        # TODO actually create some kind of Filter object.
        self.filter_stack.append(self._verify_brace(tokens, 'filter'))


    def _get_filters(self):
        return self.filter_stack.copy()


    def _get_group(self, name):
        return UNRECOGNIZED_GROUP_NAME.get(self.all_groups, name)


    def _process_group(self, tokens):
        assert self.current_chunk is None
        tokens = self._verify_brace(tokens, 'group')
        tokens, = GROUPNAME_SINGLE.pad(tokens, 1, 1) # single token...
        tokens, = GROUPNAME_SINGLE.pad(tokens, 1, 1) # with a single part
        self.current_chunk = Chunk(
            self.position, self._get_filters(), self._get_group(tokens)
        )


    def _close_directive(self):
        if self.current_chunk is not None: # close the chunk
            chunk = self.current_chunk
            # Estimate position after the chunk.
            # This will *normally* give the correct value, but some
            # filters could conceivably mess it up.
            self.position += chunk.size
            # Push chunk onto a list to be properly resolved later.
            self.chunks.append(chunk)
            self.current_chunk = None
        else:
            UNMATCHED_BRACE.convert(IndexError, self.filter_stack.pop)


    def add_line(self, indent, tokens):
        # Indentation is irrelevant.
        assert tokens # empty lines were preprocessed out.
        first, *rest = tokens
        # FIXME: relax this restriction if/when implicit struct names
        # are implemented for single-struct groups.
        first, = BAD_LINE_START.pad(first, 1, 1)
        if first.startswith('@'):
            DIRECTIVE_INSIDE_CHUNK.require(self.current_chunk is None)
            self._dispatch(first[1:], rest)
        elif first == '}':
            JUNK_AFTER_CLOSE_BRACE.require(not rest)
            self._close_directive()
        else:
            NON_DIRECTIVE_OUTSIDE_CHUNK.require(self.current_chunk is not None)
            self.current_chunk.add_line(tokens)


    def end_file(self, label, accumulator):
        # Ignore file-based label suggestion; add multiple chunks based on
        # file contents to the accumulator.
        for chunk in self.chunks:
            key, value = chunk.complete(self.labels)
            DUPLICATE_CHUNK_LOCATION.add_unique(accumulator, key, value)
