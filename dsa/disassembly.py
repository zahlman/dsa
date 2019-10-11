from .errors import wrap as wrap_errors, UserError
from .parsing.line_parsing import output_line
from .ui.tracing import trace
from itertools import count


class CHUNK_TYPE_CONFLICT(UserError):
    """conflicting requests for parsing data at 0x{where:X}"""


class _InterpreterWrapper:
    def __init__(self, name, impl, config):
        self._name, self._impl, self._config = name, impl, config


    @property # read-only
    def name(self):
        return self._name


    @property
    def args(self):
        return (self._name, *self._config)


    def disassemble(self, label, data, register, label_ref):
        return self._impl.disassemble(
            self._config, label, data, register, label_ref
        )


class _DummyChunk:
    def __init__(self, group_args, label):
        # We might have "unrecognized" group args that we need to check later.
        self._group_args = group_args
        self._label = label


    @property # read-only
    def label(self):
        return self._label


    @property
    def size(self):
        return 0


    @property # read-only
    def group_name(self):
        return '' if self._group_args is None else self._group_args[0]


    def match_args(self, args):
        return args == self._group_args


    def load(self, register, label_ref):
        pass


    def write_to(self, outfile, location):
        name = self.group_name
        output_line(outfile, [f'@@{name}'], [self.label], [f'0x{location:X}'])
        outfile.write('@@\n\n')


class _Chunk:
    def __init__(self, interpreter, tag, unpack_chain, label):
        assert isinstance(interpreter, _InterpreterWrapper)
        self._interpreter = interpreter
        self._tag, self._label = tag, label
        self._data, self._tokens = unpack_chain.data, unpack_chain.tokens
        self._lines, self._size = None, 0


    @property # read-only
    def label(self):
        return self._label


    @property # read-only
    def size(self):
        return self._size


    @property # read-only
    def group_name(self):
        return self._interpreter.name


    def match_args(self, args):
        return args == self._interpreter.args


    def load(self, register, label_ref):
        self._size, self._lines = wrap_errors(
            self._tag, self._interpreter.disassemble,
            self._label, self._data, register, label_ref
        )


    def write_to(self, outfile, location):
        for line in self._tokens(self._size):
            output_line(outfile, *line)
        name = self.group_name
        output_line(outfile, [f'@@{name}'], [self.label], [f'0x{location:X}'])
        for line in self._lines:
            output_line(outfile, *line)
        outfile.write(f'@@ #0x{location+self._size:X}\n\n')


class Disassembler:
    def __init__(
        self, source, group_lookup, filter_library,
        root_group_name, root_location
    ):
        self._source = source
        self._group_lookup = group_lookup
        self._filter_library = filter_library
        self._chunks = {} # position -> Chunk (disassembled or pending)
        self._pending = set() # positions of pending Chunks
        self._labels = set() # string label names of Chunks
        # For now, no parameters for the root group.
        self._register((root_group_name,), (), root_location, 'main')


    def _make_label(self, base):
        for i in count(1):
            suggestion = base if i == 1 else f'{base} {i}'
            if suggestion not in self._labels:
                return suggestion


    def _next_chunk(self):
        try:
            position = min(self._pending)
            self._pending.remove(position)
        except ValueError: # empty set, so min() failed before .remove()
            return None
        return position, self._chunks[position]


    def _init_chunk(self, group_args, filter_specs, start, label):
        if group_args is None: # no referent was specified at all
            # so we just set up a labelled, empty block.
            return _DummyChunk(group_args, label)
        # Otherwise, try to create an interpreter wrapper.
        group_name, *group_config = group_args
        group = self._group_lookup.get(group_name, None)
        if group is None:
            trace(f'Warning: will skip chunk of unknown type {group_name}')
            return _DummyChunk(group_args, label)
        # We have a valid group.
        interpreter = _InterpreterWrapper(group_name, group, group_config)
        tag = f'Structgroup {group_name} (chunk starting at 0x{start:X})'
        unpack_chain = self._filter_library.unpack_chain(
            self._source, start, filter_specs
        )
        return _Chunk(interpreter, tag, unpack_chain, label)


    def _register(self, group_args, filter_specs, location, label_base):
        if location in self._chunks:
            CHUNK_TYPE_CONFLICT.require(
                self._chunks[location].match_args(group_args),
                where=location
            )
        else:
            label = self._make_label(label_base)
            self._chunks[location] = self._init_chunk(
                group_args, filter_specs, location, label
            )
            self._pending.add(location)
            self._labels.add(label)


    def _label_ref(self, location):
        if location not in self._chunks:
            return f'0x{location}:X' # i.e., keep a raw value.
            # FIXME: will bias/stride/etc. mess with this?
        # NULL pointers should have been handled by the referent-getting logic.
        return f'@{self._chunks[location].label}'


    def _write_to(self, outfile):
        for location, chunk in sorted(self._chunks.items()):
            chunk.write_to(outfile, location)


    def __call__(self, outfilename):
        for position, chunk in iter(self._next_chunk, None):
            chunk.load(self._register, self._label_ref)
        with open(outfilename, 'w') as outfile:
            self._write_to(outfile)
