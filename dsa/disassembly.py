from .errors import wrap as wrap_errors, UserError
from .parsing.line_parsing import format_line, wrap_multiword
from .ui.tracing import trace
from itertools import count


class CHUNK_TYPE_CONFLICT(UserError):
    """conflicting requests for parsing data at 0x{where:X}"""


class Disassembler:
    def __init__(self, structgroups, root, location, label_base):
        self.labels = {} # position -> label
        self.used_groups = {} # position -> name of structgroup
        self.sizes = {} # position -> size of chunk data
        self.chunks = {} # position -> disassembled chunk
        self.pending_groups = {} # position -> name of structgroup
        self.all_groups = structgroups # name -> StructGroup instance
        self.add(root, location, label_base)


    def get_label(self, location, base):
        if location in self.labels:
            return self.labels[location]
        used = set(self.labels.values())
        for i in count(1):
            suggestion = base if i == 1 else f'{base} {i}'
            if suggestion not in used:
                self.labels[location] = suggestion
                return suggestion


    def _store_result(self, location, group_name, chunk, size):
        self.used_groups[location] = group_name
        self.chunks[location] = chunk
        self.sizes[location] = size


    def _make_chunk(self, source, location, group, group_name):
        position = location
        previous = None
        lines = []
        group.check_alignment(position)
        for i in count():
            result = wrap_errors(
                f'Structgroup {group_name} (chunk starting at 0x{location:X})',
                group.format_from, source, position, previous, i, self
            )
            if result is None:
                position += group.terminator_size
                break
            # TODO: possibly get new chunk requests here.
            previous, (tokens, size) = result
            lines.extend(format_line((previous,) + tokens))
            position += size
        return lines, position - location


    def add(self, group_name, location, label_base):
        if location in self.used_groups:
            CHUNK_TYPE_CONFLICT.require(
                group_name == self.used_groups[location], where=location
            )
        elif location in self.pending_groups:
            CHUNK_TYPE_CONFLICT.require(
                group_name == self.pending_groups[location], where=location
            )
        else:
            if not 0 <= location:
                # This is a stopgap until referents are fixed properly.
                trace(f'Warning: skipping chunk at negative address')
                return 'NULL'
            else:
                self.pending_groups[location] = group_name
        return self.get_label(location, label_base)


    def _process_one(self, source):
        # Grab the next chunk to process.
        location = next(iter(self.pending_groups.keys()))
        group_name = self.pending_groups.pop(location)
        try:
            group = self.all_groups[group_name]
        except KeyError: # skip chunk for unknown group
            trace(f'Warning: skipping chunk of unknown type {group_name}')
        else:
            chunk, size = self._make_chunk(source, location, group, group_name)
            self._store_result(location, group_name, chunk, size)


    def _write_chunk(self, outfile, location):
        group_name = wrap_multiword(self.used_groups[location])
        size = self.sizes[location]
        chunk = self.chunks[location]
        outfile.write(f'@filter size {size} {{\n')
        outfile.write(f'@group {group_name} {{\n')
        for line in chunk:
            outfile.write(f'{line}\n')
        outfile.write('}\n')
        outfile.write(f'}} # end:0x{location+size:X}\n')


    def _dump(self, outfile):
        for location in sorted(self.labels.keys()):
            label = wrap_multiword(self.labels[location])
            outfile.write(f'@label {label} 0x{location:X}\n')
            if location in self.chunks:
                self._write_chunk(outfile, location)
            outfile.write('\n')


    def __call__(self, source, outfilename):
        while self.pending_groups:
            self._process_one(source)
        with open(outfilename, 'w') as outfile:
            self._dump(outfile)
