from .errors import wrap as wrap_errors, UserError
from .parsing.line_parsing import format_line, wrap_multiword
from .ui.tracing import trace
from itertools import count


class CHUNK_TYPE_CONFLICT(UserError):
    """conflicting requests for parsing data at 0x{where:X}"""


class _Chunk:
    def __init__(self, group_name, group, tag, view, label):
        self._group_name, self._group = group_name, group
        self._tag, self._view, self._label = tag, view, label
        self._lines, self._size, self._loaded = [], 0, False


    @property # read-only
    def label(self):
        return self._label


    @property # read-only
    def size(self):
        return self._size


    @property # read-only
    def group_name(self):
        return self._group_name


    def _match_data(self):
        previous = None
        offset = 0
        extract = self._group.extract
        for i in count():
            result = wrap_errors(
                self._tag, extract, self._view.get, offset, previous, i
            )
            if result is None:
                self._size = offset + self._group.terminator_size
                break
            previous, match, referents, size = result
            offset += size
            yield previous, match, referents, offset


    def load(self, register, label_ref):
        if self._group is None:
            # Since it's popped from the `_pending` set, it won't be tried again.
            return
        for struct_name, match, referents, position in self._match_data():
            for referent in referents:
                register(*referent)
            self._lines.extend(format_line(self._group.format(
                f'Struct {struct_name} (at 0x{position:X})',
                struct_name, match, label_ref
            )))
        self._loaded = True


    def write_to(self, outfile, location):
        label = wrap_multiword(self._label)
        write = outfile.write
        self._view.write_params(self._size, outfile)
        name = self._group_name or ''
        write(f'@@{name} {label} 0x{location:X}\n')
        for line in self._lines:
            write(f'{line}\n')
        if self._loaded:
            write(f'@@ #0x{location+self._size:X}\n\n')
        else:
            write('@@\n\n')


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
        self._register(root_group_name, (), root_location, 'main')


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


    def _init_chunk(self, group_name, filter_specs, start, label):
        group = self._group_lookup.get(group_name, None)
        if group is None:
            trace(f'Warning: will skip chunk of unknown type {group_name}')
            tag = None # shouldn't ever attempt to load anyway.
        else:
            group.check_alignment(start)
            tag = f'Structgroup {group_name} (chunk starting at 0x{start:X})'
        view = self._filter_library.chain(filter_specs, self._source, start)
        return _Chunk(group_name, group, tag, view, label)


    def _register(self, group_name, filter_specs, location, label_base):
        if location in self._chunks:
            CHUNK_TYPE_CONFLICT.require(
                group_name == self._chunks[location].group_name,
                where=location
            )
        else:
            label = self._make_label(label_base)
            self._chunks[location] = self._init_chunk(
                group_name, filter_specs, location, label
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
