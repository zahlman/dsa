from dsa.parsing.line_parsing import Quoted, line_parser
from dsa.parsing.token_parsing import single_parser
import os


# an interpreter is a module that replaces the parsing and formatting
# functionality of a structgroup.


_file_name_parser = line_parser(
    'filename', single_parser('name', 'string'), required=1
)


def disassemble(config, chunk_label, data, register, label_ref):
    """Produce formatted file contents for the chunk.
    In this case, we produce a line with a filename, and write the file;
    we ignore the `register` and `label_ref` callbacks completely since the
    file contents will not be examined for pointers or labels.
    `config` -> additional parameters specified by the Pointer to the chunk.
    `chunk_label` -> label that will be applied to the chunk.
    `data` -> underlying chunk data.
    `register` -> callback to request disassembling another chunk.
    `label_ref` -> callback to retrieve label text for a pointer."""
    # TODO: use `config` to determine the file extension.
    filename = f'{chunk_label}.dat'
    with open(filename, 'wb') as f:
        f.write(data)
    # One line with one token that is the filename.
    return len(data), [[Quoted(filename)]]


def item_size(name):
    """Determine the amount of bytes corresponding to a chunk line,
    according to the first token of the line (must be single-part).
    In this case, that token is a file name, so we report its size."""
    return os.stat(name).st_size


def assemble(lines):
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
