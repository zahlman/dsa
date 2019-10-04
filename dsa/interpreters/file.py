from dsa.parsing.line_parsing import line_parser
from dsa.parsing.token_parsing import single_parser
import os


# an interpreter is a module that replaces the parsing and formatting
# functionality of a structgroup.


_file_name_parser = line_parser(
    'filename', single_parser('name', 'string'), required=1
)


class Interpreter:
    @property
    def alignment(self):
        """Intrinsic alignment of the chunk. Offset in the underlying binary
        data must be a multiple of this value."""
        return 1


    def disassemble(self, chunk_label, get, register, label_ref):
        """Produce formatted file contents for the chunk.
        In this case, we produce a line with a filename, and write the file;
        we ignore the `register` and `label_ref` callbacks completely since the
        file contents will not be examined for pointers or labels.
        `get` -> accessor for the underlying chunk data.
        `register` -> callback to request disassembling another chunk.
        `label_ref` -> callback to retrieve label text for a pointer."""
        data = get(0, None)
        filename = f'{chunk_label}.dat'
        with open(filename, 'wb') as f:
            f.write(data)
        # triple list here: lines -> tokens -> token parts.
        return len(data), [[[filename]]]


    def item_size(self, name):
        """Determine the amount of bytes corresponding to a chunk line,
        according to the first token of the line (must be single-part).
        In this case, that token is a file name, so we report its size."""
        return os.stat(name).st_size


    def assemble(self, lines):
        """Produce raw data representing the chunk for the binary.
        The `lines` have already had labels resolved.
        When assembling, we allow multiple file names - one per line -
        and concatenate the file contents."""
        result = bytearray()
        for line in lines:
            filename, = _file_name_parser(line)
            with open(filename, 'rb') as f:
                result.extend(f.read())
        return bytes(result)
