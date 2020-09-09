# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

from .errors import wrap as wrap_errors, UserError
from .output import output_file
from .ui.tracing import my_tracer
from itertools import count


class CHUNK_TYPE_CONFLICT(UserError):
    """chunk type conflict at 0x{where:X}: `{current}` vs. `{previous}`"""


class MISALIGNED_CHUNK(UserError):
    """chunk location 0x{where:X} invalid; must be a multiple of {align}"""


class _InterpreterWrapper:
    def __init__(self, name, impl, config):
        self._name, self._impl, self._config = name, impl, config


    @property # read-only
    def name(self):
        return self._name


    @property
    def args(self):
        return (self._name, *self._config)


    def disassemble(self, codec_lookup, label, data, register, label_ref):
        return self._impl.disassemble(
            codec_lookup, self._config, label, data, register, label_ref
        )


def _chunk_header(label, location, name):
    return ('!', ('@', label), (f'0x{location:X}',), name)


def _format_args(args):
    return '<unknown>' if args is None else ', '.join(args)


class _DummyChunk:
    def __init__(self, interpreter_args, label):
        # We might have "unrecognized" args that we need to check later.
        self._interpreter_args = interpreter_args
        self._label = label


    @property # read-only
    def label(self):
        return self._label


    @property
    def size(self):
        return 0


    def verify_args(self, args, where):
        CHUNK_TYPE_CONFLICT.require(
            args == self._interpreter_args, where=where,
            current=_format_args(args),
            previous=_format_args(self._interpreter_args)
        )


    def load(self, codec_lookup, register, label_ref):
        pass


    def tokens(self, location):
        name = '' if self._interpreter_args is None else self._interpreter_args
        yield _chunk_header(self._label, location, name)
        yield ('!',)
        yield ('',)


class _Chunk:
    def __init__(self, interpreter_args, interpreter, tag, unpack_chain, label):
        assert isinstance(interpreter, _InterpreterWrapper)
        self._interpreter = interpreter
        self._tag, self._label = tag, label
        self._data, self._filter_info = unpack_chain.data, unpack_chain.info
        self._lines, self._size = None, 0
        self._interpreter_args = interpreter_args


    @property # read-only
    def label(self):
        return self._label


    @property # read-only
    def size(self):
        return self._size


    def verify_args(self, args, where):
        # FIXME: Does it make sense to handle this the same way?
        CHUNK_TYPE_CONFLICT.require(
            args == self._interpreter_args, where=where,
            previous=', '.join(self._interpreter_args), current=', '.join(args)
        )


    def load(self, codec_lookup, register, label_ref):
        self._size, self._lines = wrap_errors(
            self._tag, self._interpreter.disassemble,
            codec_lookup, self._label, self._data, register, label_ref
        )


    def tokens(self, location):
        lines, size = self._filter_info(self._size)
        yield from lines # filters
        name = self._interpreter_args
        yield _chunk_header(self._label, location, name) # interpreter
        yield from self._lines # chunk
        yield ('!', (f'# 0x{location+size:X}',))
        yield ('',)


class Disassembler:
    def __init__(
        self, source, interpreter_lookup, filter_library, codec_lookup, root_data
    ):
        self._source = source
        self._interpreter_lookup = interpreter_lookup
        self._filter_library = filter_library
        self._codec_lookup = codec_lookup
        self._chunks = {} # position -> Chunk (disassembled or pending)
        self._pending = set() # positions of pending Chunks
        self._labels = set() # string label names of Chunks
        # Using normal tokenization rules is probably not desirable.
        # Just split the "root" data on colons, use the last for the location,
        # and others for name and parameters.
        root_name, root_params, root_location = root_data
        self._register((root_name, *root_params), (), root_location, 'main')


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


    def _init_chunk(self, interpreter_args, filter_specs, start, label):
        if interpreter_args is None: # no referent was specified at all
            # so we just set up a labelled, empty block.
            return _DummyChunk(interpreter_args, label)
        # Otherwise, try to create an interpreter wrapper.
        interpreter_name, *interpreter_config = interpreter_args
        interpreter = self._interpreter_lookup.get(interpreter_name, None)
        if interpreter is None:
            my_tracer.trace(
                f'Warning: will skip chunk of unknown type {interpreter_name}'
            )
            return _DummyChunk(interpreter_args, label)
        # We have a valid interpreter. Is the `start` aligned to its spec?
        MISALIGNED_CHUNK.require(
            not start % interpreter.alignment,
            where=start, align=interpreter.alignment
        )
        interpreter = _InterpreterWrapper(interpreter_name, interpreter, interpreter_config)
        tag = f'Interpreter {interpreter_name} (chunk starting at 0x{start:X})'
        unpack_chain = self._filter_library.unpack_chain(
            self._codec_lookup, self._source, start, filter_specs
        )
        return _Chunk(interpreter_args, interpreter, tag, unpack_chain, label)


    def _register(self, interpreter_args, filter_specs, location, label_base):
        if location in self._chunks:
            self._chunks[location].verify_args(interpreter_args, location)
            return
        label = self._make_label(label_base)
        self._chunks[location] = self._init_chunk(
            interpreter_args, filter_specs, location, label
        )
        self._pending.add(location)
        self._labels.add(label)


    def _label_ref(self, location):
        if location not in self._chunks:
            return (f'0x{location:X}',) # i.e., keep a raw value.
            # FIXME: will bias/stride/etc. mess with this?
        # NULL pointers should have been handled by the referent-getting logic.
        return ('@', self._chunks[location].label)


    def _all_tokens(self):
        for location, chunk in sorted(self._chunks.items()):
            yield from chunk.tokens(location)


    def __call__(self, outfilename):
        for position, chunk in iter(self._next_chunk, None):
            chunk.load(self._codec_lookup, self._register, self._label_ref)
        output_file(outfilename, self._all_tokens())
