from dsa.parsing.line_parsing import line_parser
from dsa.parsing.token_parsing import single_parser
import os


# An interpreter is a module that replaces the parsing and formatting
# functionality of a structgroup.


_file_name_token = single_parser('name', 'string')
_file_name_line = line_parser('filename', _file_name_token, required=1)


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
    # One line with an empty prefix and one token that is the filename.
    # repr() makes this a quoted token that won't be mangled later.
    return len(data), (('', (repr(filename),)),)


def item_size(token):
    """Determine the amount of bytes corresponding to a chunk line,
    according to the first token of the line. In this case, we parse a
    file name out of the token, and report that file's size."""
    return os.stat(_file_name_token(token)).st_size


def assemble(lines):
    """Produce raw data representing the chunk for the binary.
    The `lines` have already had labels resolved.
    When assembling, we allow multiple file names - one per line -
    and concatenate the file contents."""
    result = bytearray()
    for line in lines:
        filename, = _file_name_line(line)
        with open(filename, 'rb') as f:
            result.extend(f.read())
    return bytes(result)
