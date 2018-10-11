import errors
import binascii
from functools import partial
import re, textwrap


class NOT_ENOUGH_PARTS(errors.UserError):
    """not enough parts for multipart token"""


class TOO_MANY_PARTS(errors.UserError):
    """too many parts for multipart token"""


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


token = re.compile('(?:\[[^\[\]]*\])|(?:[^ \t\[\]]+)')


def tokenize(line):
    # Also normalizes whitespace within bracketed tokens.
    # We need to do this to avoid e.g. issues with multi-word identifiers
    # (like 'foo bar' not matching 'foo\tbar'), which gets that much hairier
    # with line-wrapping involved.
    return [
        x[1:-1] if x.startswith('[') else x
        for x in token.findall(' '.join(line.split()))
    ]


# FIXME
def parts_of(token, separator, required, allowed, last_list):
    parts = [
        x.strip() if x.strip() else None
        for x in token.split(separator)
    ]
    count = len(parts)
    NOT_ENOUGH_PARTS.require(count >= required)
    if count < allowed:
        padding = allowed - count - (1 if last_list else 0)
        parts.extend([None] * padding)
    if last_list: # group up the last token, even if padding occurred.
        parts = parts[:allowed-1] + [parts[allowed-1:]]
    else:
        TOO_MANY_PARTS.require(count <= allowed)
    return parts


# Used as the final step in producing output when disassembling.
def format_line(tokens):
    tokens = [
        t if t == ''.join(t.split()) else f'[{t}]'
        for t in tokens
    ]
    return textwrap.wrap(
        ' '.join(tokens), width=78,
        # Indicate the wrapped lines according to spec.
        subsequent_indent=' ' * len(tokens[0]) + ' + ',
        # Ensure that `textwrap` doesn't alter anything important.
        break_long_words=False, break_on_hyphens=False
    )


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
