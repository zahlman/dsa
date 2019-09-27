from dsa.parsing.line_parsing import integer
# Any exception raised by the application of a filter will be converted at
# a higher level. Note that additional parameters will not have been parsed;
# each will be a sequence representing a possibly-multipart token.
# Since these modules will be dynamically imported, they should use absolute
# imports for DSA parsing utilities.


# Converts a chunk of data into the form it takes in the binary, e.g.
# by applying compression, encryption etc. Any parameters after the first are
# taken from the @ line in the data description file that specified the filter.
def pack(data, size):
    size = integer(size)
    padding = size - len(data)
    if padding < 0:
        raise ValueError(
            f'too much data ({len(data)} bytes; expected at most {size})'
        )
    return data + bytes(padding)


# Provides a view into the original source data from a specified base
# location onwards, as if it had never been pack()ed.
class View:
    """Represents unfiltered data, but tracks the size of the chunk implied
    by read operations during disassembly."""


    # `source` and `base` are determined by disassembly; any additional
    # parameters come from the type specification of the pointer to this
    # chunk. For the `size` filter there are no such parameters.
    def __init__(self, source, base):
        self._source = source
        self._base = base
        self._size = 0


    # return an [offset:offset+size] slice of the virtual data.
    # The caller promises that `offset` and `size` are nonnegative.
    def get(self, offset, size):
        location = self._base + offset
        self._size = max(self._size, offset+size)
        return self._source[location:location+size]


    # return the tokens needed to indicate this filter in the
    # data description file.
    def params(self):
        return ((str(self._size),),)
