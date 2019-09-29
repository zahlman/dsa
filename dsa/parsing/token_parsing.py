from ..errors import MappingError, UserError
import binascii
from functools import partial


class TOO_MANY_PARTS(UserError):
    """{description} token had extra unallowed parts `{token}`"""


class MULTIPART(UserError):
    """multi-part token `{token}` not allowed for {description}"""


class BAD_INTEGER(UserError):
    """{description} must be integer (got `{token}`)"""


class ILLEGAL_VALUE(MappingError):
    """`{key}` is not a valid value for {description}; must be one of {allowed}"""


class MUST_BE_POSITIVE(UserError):
    """value cannot be negative or zero"""


class INVALID_BOOLEAN(MappingError):
    """invalid boolean `{key}` for {description} (must be `true` or `false`, case-insensitive)"""


class INVALID_BASE(MappingError):
    """invalid base setting `{key}` for {description} (allowed values: 2, 8, 10, 16)"""


class INVALID_HEXDUMP(UserError):
    """invalid hex dump for {description}"""


class EMPTY_TOKEN(UserError):
    """empty token is not allowed for {description}"""
    # An empty token could be created by `[]`.


# Conversions for tokens to other types.
def empty(token, description):
    TOO_MANY_PARTS.require(not token, token=token, description=description)
    return None


def string(token, description):
    EMPTY_TOKEN.require(token is not None, description=description)
    MULTIPART.require(len(token) == 1, token=token, description=description)
    return token[0]


def optional_string(token, description):
    # FIXME handle None tokens more gracefully vs empty-string token parts?
    return None if token is None else string(token, description)


def integer(token, description):
    # FIXME UserError.convert can't do this.
    try:
        return int(token[0], 0)
    except ValueError as e:
        raise BAD_INTEGER(reason=str(e), token=token, description=description) from e


def optional_integer(token, description):
    # FIXME this is ugly. 
    return None if (token is None or token == ['']) else integer(token, description)


def _whitelisted_string(whitelist, token, description):
    result = string(token, description)
    return ILLEGAL_VALUE.get(
        whitelist, result,
        allowed=whitelist, description=description
    )


def one_of(*values):
    return partial(_whitelisted_string, {x:x for x in values})


def converting(**values):
    return partial(_whitelisted_string, values)


def positive_integer(token, description):
    result = integer(token, description)
    MUST_BE_POSITIVE.require(result > 0)
    return result


def boolean(token, description):
    if not token:
        return True # shortcut syntax
    text = string(token)
    return INVALID_BOOLEAN.get({'true': True, 'false': False}, text.lower())


def base(token, description):
    text = string(token, description)
    return INVALID_BASE.get({'2': bin, '8': oct, '10': str, '16': hex}, text)


def hexdump(token, description):
    text = ''.join(string(token, description).split())
    return INVALID_HEXDUMP.convert(binascii.Error, binascii.unhexlify, text)


def make_set(token, description):
    return set(token) # FIXME detect errors / care about description


# For multipart tokens where the first part is a label.
def _labelled(converter, token, description):
    label, content = EMPTY_TOKEN.shift(token)
    return label, converter(content)


def labelled(converter):
    return partial(_labelled, converter)
