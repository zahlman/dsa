def _resolve_labels_sub(part, label_lookup):
    if not part.startswith('@'):
        return part
    try:
        # It will get converted back to int later. FIXME this parsing is hax
        return str(label_lookup[part[1:]])
    except KeyError:
        raise ValueError('unrecognized label `@{part}`')


def _resolve_labels(line, label_lookup):
    result = [
        ', '.join(
            _resolve_labels_sub(part.strip(), label_lookup)
            for part in token.split(',')
        )
        for token in line
    ]
    return result


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
        for line in self.lines:
            previous, data = self.group.parse(
                _resolve_labels(line, label_lookup), previous
            )
            result.extend(data)
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


    def _dispatch(self, directive, rest):
        try:
            handler = {
                'label': self._process_label,
                'filter': self._process_filter,
                'group': self._process_group
            }[directive]
        except KeyError:
            raise ValueError(f'unrecognized directive `{first}`')
        handler(rest)


    def _process_label(self, tokens):
        count = len(tokens)
        if count > 2:
            raise ValueError(f'too many arguments for `@label` directive')
        elif count == 2:
            name, position = tokens
            self.position = int(position, 0)
        elif count == 1:
            name = tokens[0]
        else:
            raise ValueError(f'missing name for label')
        self.labels[name] = self.position


    def _verify_brace(self, tokens, dname):
        if not tokens:
            raise ValueError(f'missing open brace for `@{dname}` directive')
        *args, brace = tokens
        if brace != '{':
            raise ValueError(f'missing open brace for `@{dname}` directive')
        return args


    def _process_filter(self, tokens):
        # TODO actually create some kind of Filter object.
        self.filter_stack.append(self._verify_brace(tokens, 'filter'))


    def _get_filters(self):
        return self.filter_stack.copy()


    def _get_group(self, name):
        try:
            return self.all_groups[name]
        except KeyError:
            raise ValueError(f'unrecognized group name `{name}`')


    def _process_group(self, tokens):
        assert self.current_chunk is None
        tokens = self._verify_brace(tokens, 'group')
        if len(tokens) == 0:
            raise ValueError(f'missing group name')
        if len(tokens) == 2:
            raise ValueError(f'junk after group name')
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
                raise ValueError(f'unmatched closing brace')


    def add_line(self, indent, tokens):
        # Indentation is irrelevant.
        assert tokens # empty lines were preprocessed out.
        first, *rest = tokens
        if first.startswith('@'):
            if self.current_chunk is not None:
                raise ValueError('Directive not allowed here')
            self._dispatch(first[1:], rest)
        elif first == '}':
            if rest:
                raise ValueError('Closing brace must be on a line by itself')
            self._close_directive()
        elif self.current_chunk is not None:
            self.current_chunk.add_line(tokens)
        else:
            raise ValueError('Syntax error (should this be inside a block?)')


    def end_file(self, label, accumulator):
        # Ignore file-based label suggestion; add multiple chunks based on
        # file contents to the accumulator.
        for chunk in self.chunks:
            key, value = chunk.complete(self.labels)
            if key in accumulator:
                raise ValueError(
                    f'Duplicate definition for chunk at 0x{key:X}'
                )
            accumulator[key] = value
