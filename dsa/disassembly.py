from .errors import wrap as wrap_errors, UserError
from .parsing.line_parsing import format_line, wrap_multiword
from .ui.tracing import trace
from itertools import count


class CHUNK_TYPE_CONFLICT(UserError):
    """conflicting requests for parsing data at 0x{where:X}"""


class _Chunk:
    def __init__(self, group_name, label):
        self._group_name = group_name
        self._label = label
        self._lines = []
        self._size = 0
        self._loaded = False


    @property # read-only
    def label(self):
        return self._label


    @property # read-only
    def size(self):
        return self._size


    @property # read-only
    def group_name(self):
        return self._group_name


    def _match_data(self, group, tag, source, position):
        previous = None
        for i in count():
            result = wrap_errors(
                tag, group.extract, source, position, previous, i
            )
            if result is None:
                self._size += group.terminator_size
                break
            previous, match, referents, size = result
            self._size += size
            position += size
            yield previous, match, referents, position


    def load(self, source, start, group_lookup, registry):
        group_name = self._group_name
        try:
            group = group_lookup[group_name]
        except KeyError: # skip chunk for unknown group
            trace(f'Warning: skipping chunk of unknown type {group_name}')
            return # we end up with an empty chunk.
        group.check_alignment(start)
        tag = f'Structgroup {group_name} (chunk starting at 0x{start:X})'
        data = self._match_data(group, tag, source, start)
        for thing in data:
            struct_name, match, referents, position = thing
            for referent in referents:
                registry.register(*referent)
            self._lines.extend(format_line(group.format(
                f'Struct {struct_name} (at 0x{position:X})',
                struct_name, match, registry.label_ref
            )))
        self._loaded = True


    def write_to(self, outfile, location):
        label = wrap_multiword(self._label)
        write = outfile.write
        if self._loaded:
            # Only add a size filter if the group was recognized.
            write(f'@size {self._size}\n')
        write(f'@@{self._group_name} {label} 0x{location:X}\n')
        for line in self._lines:
            write(f'{line}\n')
        if self._loaded:
            write(f'@@ #0x{location+self._size:X}\n\n')
        else:
            write('@@\n\n')


class _ChunkRegistry:
    def __init__(self, root_group_name, root_location):
        self._chunks = {} # position -> Chunk (disassembled or pending)
        self._pending = set() # positions of pending Chunks
        self._labels = set() # string label names of Chunks
        self.register(root_group_name, root_location, 'main')


    def _make_label(self, base):
        for i in count(1):
            suggestion = base if i == 1 else f'{base} {i}'
            if suggestion not in self._labels:
                return suggestion


    def next_chunk(self):
        try:
            position = self._pending.pop()
        except KeyError:
            return None
        return position, self._chunks[position]


    def register(self, group_name, location, label_base):
        if location in self._chunks:
            CHUNK_TYPE_CONFLICT.require(
                group_name == self._chunks[location].group_name,
                where=location
            )
        elif location < 0:
            # FIXME?
            trace(f'Warning: skipping chunk at negative address')
        else:
            label = self._make_label(label_base)
            self._chunks[location] = _Chunk(group_name, label)
            self._pending.add(location)
            self._labels.add(label)


    def label_ref(self, location):
        if location not in self._chunks:
            # FIXME handle null pointers a better way.
            return 'NULL' if location == 0 else 'UNKNOWN'
        return f'@{self._chunks[location].label}'


    def write_to(self, outfile):
        for location, chunk in sorted(self._chunks.items()):
            chunk.write_to(outfile, location)


class Disassembler:
    def __init__(self, group_lookup, group_name, filter_lookup, location):
        self._registry = _ChunkRegistry(group_name, location)
        self._group_lookup = group_lookup
        # FIXME: Filters are ignored for now when disassembling.
        self._filter_lookup = filter_lookup


    def __call__(self, source, outfilename):
        for position, chunk in iter(self._registry.next_chunk, None):
            chunk.load(source, position, self._group_lookup, self._registry)
        with open(outfilename, 'w') as outfile:
            self._registry.write_to(outfile)
