from dsa.parsing.line_parsing import line_parser
from dsa.parsing.token_parsing import single_parser
# Any exception raised by the application of a filter will be converted at
# a higher level. Note that additional parameters will not have been parsed;
# each will be a sequence representing a possibly-multipart token.
# Since these modules will be dynamically imported, they should use absolute
# imports for DSA parsing utilities.


# Converts a chunk of data into the form it takes in the binary, e.g.
# by applying compression, encryption etc. Any parameters after the first are
# taken from the @ line in the data description file that specified the filter.
def pack(data, params):
    size, = line_parser(
        '`size` filter parameters',
        single_parser('chunk size', 'integer')
    )(params)
    padding = size - len(data)
    if padding < 0:
        raise ValueError(
            f'too much data ({len(data)} bytes; expected at most {size})'
        )
    return data + bytes(padding)


# Provides a view into the original source data from a specified base
# location onwards, as if it had never been pack()ed.
class View:
    """Represents unfiltered data, but may limit the amount of data."""


    # `base_get` comes from the disassembly process, and is a function
    # that provides access to data for disassembly with the same interface
    # as the `get` method. It may be either the `get` method of another
    # View instance, or a wrapper function that directly accesses the binary
    # being disassembled.
    # `params` are determined by the Pointer type specification in a type
    # definition file. This is a list of tokens (i.e. list of lists of strings)
    # that does not necessarily match what `params` outputs.
    def __init__(self, base_get, params):
        # If a size is specified by the caller, truncate reads past
        # that point; otherwise infer size from the reads.
        self._base_get = base_get
        self._limit, = line_parser(
            '`size` filter parameters',
            single_parser('chunk size limit', 'integer?')
        )(params)


    # return an [offset:offset+size] slice of the virtual data.
    # The caller promises that `offset` and `size` are nonnegative.
    # `size` may be None, indicating that the remainder of the data past
    # `offset` should be returned.
    def get(self, offset, size):
        if self._limit is not None:
            remaining = self._limit - offset
            size = remaining if size is None else min(size, remaining)
        return self._base_get(offset, size)


    # The tokens needed to represent this filter in the
    # data description file. When assembling, those tokens will be passed
    # to `pack`.
    def params(self, size):
        if self._limit is not None:
            size = min(size, self._limit)
        return [[str(size)]]
