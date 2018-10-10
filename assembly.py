import errors


class UNRECOGNIZED_LABEL(errors.MappingError):
    """unrecognized label `@{key}`"""


class UNRECOGNIZED_DIRECTIVE(errors.MappingError):
    """unrecognized directive `@{key}`"""


class LABEL_TOOMANYARGS(errors.UserError):
    """too many arguments for `@label` directive"""


class LABEL_NONAME(errors.UserError):
    """missing name for `@label` directive"""


class MISSING_BRACE(errors.UserError):
    """missing open brace for `@{directive}` directive"""


class UNRECOGNIZED_GROUP_NAME(errors.MappingError):
    """unrecognized group name `{key}`"""


class GROUPNAME_MISSING(errors.UserError):
    """missing group name"""


class GROUPNAME_EXTRA(errors.UserError):
    """junk after group name"""


class UNMATCHED_BRACE(errors.UserError):
    """unmatched closing brace"""


class DIRECTIVE_INSIDE_CHUNK(errors.UserError):
    """directives not allowed inside `@group` block"""


class JUNK_AFTER_CLOSE_BRACE(errors.UserError):
    """closing brace must be on a line by itself"""


class NON_DIRECTIVE_OUTSIDE_CHUNK(errors.UserError):
    """non-directive lines must be inside `@group` blocks"""


class DUPLICATE_CHUNK_LOCATION(errors.MappingError):
    """duplicate definition for chunk at 0x{key:X}"""


def _resolve_labels_sub(part, label_lookup):
    if not part.startswith('@'):
        return part
    label = part[1:]
    return str(UNRECOGNIZED_LABEL.get(label_lookup, label))
    # It will get converted back to int later. FIXME this parsing is hax


def _resolve_labels(line, label_lookup):
    return [
        ', '.join(
            _resolve_labels_sub(part.strip(), label_lookup)
            for part in token.split(',')
        )
        for token in line
    ]


class _DummyLookup(dict):
    def __missing__(self, key):
        return 0


_dummy_lookup = _DummyLookup()


class Chunk:
    def __init__(self, location, filters, group):
        self.location = location
        self.filters = filters
        self.group = group
        self.lines = []


    def add_line(self, tokens):
        self.lines.append(tokens)


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
        count = len(tokens)
        LABEL_TOOMANYARGS.require(count <= 2)
        LABEL_NONAME.require(count > 0)
        if count == 2:
            name, position = tokens
            self.position = errors.parse_int(position)
        else:
            assert count == 1
            # Use the existing value for self.position.
            name, = tokens
        self.labels[name] = self.position


    def _verify_brace(self, tokens, dname):
        MISSING_BRACE.require(bool(tokens), directive=dname)
        *args, brace = tokens
        MISSING_BRACE.require(brace == '{', directive=dname)
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
        count = len(tokens)
        GROUPNAME_MISSING.require(count > 0)
        GROUPNAME_EXTRA.require(count < 2)
        self.current_chunk = Chunk(
            self.position, self._get_filters(), self._get_group(tokens[0])
        )


    def _close_directive(self):
        if self.current_chunk is not None: # close the chunk
            chunk = self.current_chunk
            # Estimate position after the chunk.
            # This will *normally* give the correct value, but some
            # filters could conceivably mess it up.
            location, value = chunk.complete(_dummy_lookup)
            assert location == self.position
            self.position += len(value)
            # Push chunk onto a list to be properly resolved later.
            self.chunks.append(chunk)
            self.current_chunk = None
        else:
            try:
                self.filter_stack.pop()
            except IndexError:
                raise UNMATCHED_BRACE


    def add_line(self, indent, tokens):
        # Indentation is irrelevant.
        assert tokens # empty lines were preprocessed out.
        first, *rest = tokens
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
