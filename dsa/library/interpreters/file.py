# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

from dsa.parsing.line_parsing import line_parser
from dsa.parsing.token_parsing import single_parser
import os


# An interpreter is a module that replaces the parsing and formatting
# functionality of a structgroup.


_filetype = single_parser('name', 'string?')
_file_name_token = single_parser('name', 'string')
_file_name_line = line_parser('filename', _file_name_token, required=1)


_SANITIZER = {
    ord(c): '_' for c in (
        # Characters that may cause problems in filenames.
        '\0', '/', # Linux and other Unix-like systems
        ':', # old MacOS path separator; can still be an issue
        '\\', '\u00a5', # Windows file separator
        # (Japanese locales may remap the yen symbol to '\\')
        '?', '*', # wildcard syntax chars; can cause problems in DOS
        '.' # hidden files (extension will be added programmatically)
    )
}


def _sanitize(name, ext):
    if ext.startswith('.'):
        ext = ext[1:] # allow it to be specified either way
    return f'{name.translate(_SANITIZER)}.{ext.translate(_SANITIZER)}'


def disassemble(codec_lookup, config, chunk_label, data, register, label_ref):
    """Produce formatted file contents for the chunk.
    In this case, we produce a line with a filename, and write the file;
    we ignore the `register` and `label_ref` callbacks completely since the
    file contents will not be examined for pointers or labels.
    `codec_lookup` -> library of codecs that might be useful here.
    `config` -> additional parameters specified by the Pointer to the chunk.
    `chunk_label` -> label that will be applied to the chunk.
    `data` -> underlying chunk data.
    `register` -> callback to request disassembling another chunk.
    `label_ref` -> callback to retrieve label text for a pointer."""
    extension = _filetype(config) or 'dat'
    filename = _sanitize(chunk_label, extension)
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


def assemble(codec_lookup, config, lines):
    """Produce raw data representing the chunk for the binary.
    The `lines` have already had labels resolved.
    When assembling, we allow multiple file names - one per line -
    and concatenate the file contents."""
    result = bytearray()
    for line in lines:
        name, ext = os.path.splitext(_file_name_line(line)[0])
        with open(_sanitize(name, ext), 'rb') as f:
            result.extend(f.read())
    return bytes(result)


alignment = 1
