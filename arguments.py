import errors
from parse_config import parts_of
import binascii
from functools import partial


class DUPLICATE_PARAMETER(errors.MappingError):
    """duplicate specification of parameter `{key}`"""


class UNRECOGNIZED_PARAMETER(errors.MappingError):
    """unrecognized parameter `{key}`"""


class MISSING_PARAMETERS(errors.UserError):
    """missing required parameters `{missing}`"""


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


class Namespace:
    def __init__(self, items):
        for key, value in items.items():
            setattr(self, key, value)


def _split_whitelist(w):
    defaults = {}
    converters = {}
    for k, v in w.items():
        if callable(v):
            converters[k] = v
        else:
            c, d = v
            converters[k] = c
            defaults[k] = d
    return defaults, converters


def arguments(tokens, parameters):
    result, converters = _split_whitelist(parameters)
    specified = {}
    for token in tokens:
        name, item = parts_of(token, ':', 1, 2, True)
        DUPLICATE_PARAMETER.add_unique(
            specified, name,
            UNRECOGNIZED_PARAMETER.get(converters, name)(item)
        )
    result.update(specified)
    missing = set(converters.keys()) - set(result.keys())
    MISSING_PARAMETERS.require(not missing, missing=missing)
    return Namespace(result)


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
    if not items:
        return True # shortcut syntax
    text = string(items)
    return INVALID_BOOLEAN.get({'true': True, 'false': False}, text.lower())


def base(items):
    text = string(items)
    return INVALID_BASE.get({'2': bin, '8': oct, '10': str, '16': hex}, text)


def hexdump(items):
    text = ''.join(string(items).split())
    return INVALID_TERMINATOR.convert(binascii.Error, binascii.unhexlify, text)
