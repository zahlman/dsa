# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

from .file_parsing import SimpleLoader
from .line_parsing import line_parser
from .token_parsing import make_parser, single_parser
from ..errors import MappingError, UserError
from ..ui.tracing import my_tracer


class UNRECOGNIZED_LABEL(MappingError):
    """unrecognized label `{key}`"""


class UNNAMED_INTERPRETER(UserError):
    """{name} chunk contains data and there is no interpreter for it"""


class UNCLOSED_CHUNK(UserError):
    """missing `!` line to close chunk before starting a new one"""


class OUTSIDE_CHUNK(UserError):
    """struct/label must be inside a chunk"""


class NO_CHUNK_DEFINITION(UserError):
    """chunk has no definition line (names the chunk and its interpreter)"""


class BAD_EMPTY_TOKEN(UserError):
    """empty token not allowed at beginning of line"""


class LABEL_CONFLICT(MappingError):
    """duplicate definition for label `{key}`"""


class DUPLICATE_CHUNK_LOCATION(MappingError):
    """duplicate definition for chunk at 0x{key:X}"""


def _resolve_labels(line, label_lookup):
    return [
        (
            [str(UNRECOGNIZED_LABEL.get(label_lookup, tuple(token)))]
            if token[0] == '@' else token
        )
        for token in line
    ]


class _DummyInterpreter:
    """A fake interpreter that works only for empty chunks, producing b''."""
    def __init__(self, name):
        self._name = name


    def assemble(self, codec_lookup, config, lines):
        UNNAMED_INTERPRETER.require(not lines, name=self._name)
        return b''


    def item_size(self, name):
        raise UNNAMED_INTERPRETER(name=self._name)


_chunk_header_parser = line_parser(
    'chunk info',
    make_parser('label', ({'@'}, 'at'), ('string', 'name')),
    single_parser('position', 'integer'),
    single_parser('interpreter', '[string'),
    required=2
)


_filter_line_parser = line_parser(
    'filter info',
    single_parser('name', 'string'),
    required=1, more=True
)


_internal_label_parser = line_parser(
    'chunk-internal label info',
    make_parser('label', ({'@'}, 'at'), ('string', 'name')),
    required=1
)


class Chunk:
    def __init__(self):
        self._location = None
        self._filters = [] # (name, tokens) filter specs.
        self._interpreter = None
        self._chunk_label = None
        self._lines = []
        self._labels = [] # (token for label, position) assuming unfiltered.
        # The token is stored as a tuple since it's used for dict lookup.
        # TODO: ensure filters won't corrupt label info.
        self._offset = 0
        self._config = None


    @property
    def has_interpreter(self):
        return self._interpreter is not None


    @property
    def labels(self):
        return self._labels


    def _set_interpreter(self, tokens, interpreter_lookup):
        UNCLOSED_CHUNK.require(not self.has_interpreter)
        chunk_label, location, interpreter_info = _chunk_header_parser(tokens)
        name, *config = interpreter_info
        self._config = config
        interpreter = interpreter_lookup.get(name, None)
        if interpreter is None:
            interpreter = _DummyInterpreter(chunk_label[1])
            if name:
                trace = my_tracer.trace
                trace(f'Warning: unrecognized interpreter name `{name}`.')
                trace('This will cause an error later if the chunk has data.')
        self._interpreter = interpreter
        self._labels.append((chunk_label, location))
        self._chunk_label, self._location = chunk_label, location


    def _add_filter(self, tokens):
        name, tokens = _filter_line_parser(tokens)
        self._filters.append((name, tokens))


    def add_meta(self, interpreter_lookup, tokens):
        BAD_EMPTY_TOKEN.require(bool(tokens[0])) # start with empty?
        if tokens[0][0] == '@':
            # first token is a label, i.e. chunk intro.
            self._set_interpreter(tokens, interpreter_lookup)
        else:
            self._add_filter(tokens)


    def _add_label(self, tokens):
        [[at, label]] = _internal_label_parser(tokens)
        self._labels.append(
            (self._chunk_label + (label,), self._location+self._offset)
        )


    def _add_struct(self, tokens):
        self._lines.append(tokens)
        self._offset += self._interpreter.item_size(tokens[0])


    def add_line(self, interpreter_lookup, tokens):
        BAD_EMPTY_TOKEN.require(bool(tokens[0]))
        # not needed for labels, but disallow them outside the header.
        OUTSIDE_CHUNK.require(self._interpreter is not None)
        if tokens[0][0] == '@':
            self._add_label(tokens)
        else:
            self._add_struct(tokens)


    def complete(self, pack_all, label_lookup, codec_lookup):
        lines = [_resolve_labels(line, label_lookup) for line in self._lines]
        return self._location, pack_all(
            codec_lookup,
            self._interpreter.assemble(
                codec_lookup, self._config, lines
            ), self._filters
        )


class SourceLoader(SimpleLoader):
    def __init__(self, interpreter_library, filter_library, codec_library):
        self._chunks = []
        self._current = None # either None or the last of the self._chunks.
        self._interpreter_lookup = interpreter_library
        self._pack_all = filter_library.pack_all
        self._codec_lookup = codec_library


    def _get_labels(self):
        labels = {}
        for chunk in self._chunks:
            for token, location in chunk.labels:
                LABEL_CONFLICT.add_unique(labels, token, location)
        return labels


    def meta(self, tokens):
        if self._current is None:
            self._current = Chunk()
            self._chunks.append(self._current)
        if not tokens: # terminator.
            NO_CHUNK_DEFINITION.require(self._current.has_interpreter)
            self._current = None
        else:
            self._current.add_meta(self._interpreter_lookup, tokens)


    def unindented(self, tokens):
        OUTSIDE_CHUNK.require(self._current is not None)
        self._current.add_line(self._interpreter_lookup, tokens)
    indented = unindented # alias; handle both cases the same way


    def result(self):
        processed = {}
        label_lookup = self._get_labels()
        for chunk in self._chunks:
            key, value = chunk.complete(
                self._pack_all, label_lookup, self._codec_lookup
            )
            DUPLICATE_CHUNK_LOCATION.add_unique(processed, key, value)
        return processed
