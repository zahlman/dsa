import errors
from parse_config import parts_of
import binascii
from functools import partial


class DUPLICATE_PARAMETER(errors.UserError):
    """duplicate specification of parameter `{name}`"""


class UNRECOGNIZED_PARAMETER(errors.MappingError):
    """unrecognized parameter `{key}`"""


class MUST_BE_SINGLE_ITEM(errors.UserError):
    """flag value must be a single item"""


class ILLEGAL_VALUE(errors.UserError):
    """value must be one of {whitelist}"""


class MUST_BE_POSITIVE(errors.UserError):
    """value cannot be negative or zero"""


class INVALID_BOOLEAN(errors.MappingError):
    """invalid boolean `{key}` (must be `true` or `false`, case-insensitive)"""


class INVALID_BASE(errors.MappingError):
    """invalid base setting `{key}` (allowed values: 2, 8, 10, 16)"""


class INVALID_TERMINATOR(errors.UserError):
    """invalid terminator format"""


def parameters(whitelist, tokens):
    result = {}
    specified = set()
    for token in tokens:
        name, item = parts_of(token, ':', 1, 2, True)
        if not item: # Shortcut for boolean flags
            item = ['True']
        DUPLICATE_PARAMETER.require(name not in specified, name=name)
        specified.add(name)
        result[name] = UNRECOGNIZED_PARAMETER.get(whitelist, name)(item)
    return result


# "types" for flag values.
def string(items):
    MUST_BE_SINGLE_ITEM.require(len(items) == 1)
    return items[0]


def integer(items):
    return errors.parse_int(string(items))


def _whitelisted_string(whitelist, items):
    result = string(items)
    ILLEGAL_VALUE.require(result in whitelist, whitelist=whitelist)
    return result


def one_of(*values):
    return partial(_whitelisted_string, values)


def positive_integer(items):
    result = integer(items)
    MUST_BE_POSITIVE.require(result > 0)
    return result


def boolean(items):
    text = string(items)
    return INVALID_BOOLEAN.get({'true': True, 'false': False}, text.lower())


def base(items):
    text = string(items)
    return INVALID_BASE.get({'2': bin, '8': oct, '10': str, '16': hex}, text)


def hexdump(items):
    text = ''.join(string(items).split())
    return INVALID_TERMINATOR.convert(binascii.Error, binascii.unhexlify, text)
