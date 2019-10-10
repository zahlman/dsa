from dsa.errors import UserError
# Since filter modules will be dynamically imported, they should use absolute
# imports for any DSA modules. non-UserError exceptions will be allowed to
# propagate and are considered programming errors; so to signal errors in the
# data, we need to import from dsa.errors.


class TOO_MUCH_DATA(UserError):
    """too much data ({actual} bytes; expected at most {expected})"""


# Parameter parser specs for packing, as a single sequence. Each pair of
# consecutive values is a name for error reporting and a parameter type
# which may be one of:
# * a tuple, list or set of allowed string values
# * a dict mapping allowed string values to parsed values
# * a string specifying a parameter type, per dsa.parsing.token_parsing
# The core code will use these to parse the filter arguments and call pack().
# The filter is responsible for ensuring the signature of pack() matches the
# arguments generated by that parser (as well as `data`).
pack_args = ('chunk size', 'integer')


# Similarly for constructing the View object.
unpack_args = ('chunk size limit', 'integer?')


# Converts a chunk of data into the form it takes in the binary, e.g.
# by applying compression, encryption etc. Any parameters after the first are
# taken from the @ line in the data description file that specified the filter.
def pack(data, size):
    padding = size - len(data)
    TOO_MUCH_DATA.require(padding >= 0, actual=len(data), expected=size)
    return data + bytes(padding)


# Provides a view into the original source data from a specified base
# location onwards, as if it had never been pack()ed.
class View:
    def __init__(self, data, limit):
        # If a size is specified, disallow access past that point.
        self._data = memoryview(data)[:limit]
        self._infer = limit is None


    # Accessor for filtered data.
    # The value returned must support the buffer interface.
    @property
    def data(self):
        return self._data


    # `unpacked`: number of bytes read by the underlying interpreter or
    # prior filter in the chain.
    # Returns (packed, params):
    # `packed`: number of bytes that will be produced by packing (may be
    # passed to the `pack_params` of the next View in the chain).
    # Normally this is just len(self.data), presuming that a buffer is
    # eagerly produced. The `size` filter, however, may determine the length
    # lazily according to the interpreted amount.
    # `params`: tokens to write in the data description file for the filter.
    # It must be a list, since the engine will prepend the name.
    def pack_params(self, unpacked):
        # If a size was specified, it is impossible that more data than
        # that was read.
        packed = unpacked if self._infer else len(self._data)
        # The data description should specify the size explicitly regardless.
        return packed, [[str(packed)]]
