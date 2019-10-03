from ..errors import MappingError, UserError
import binascii, codecs
from functools import partial


class WRONG_PART_COUNT(UserError):
    """{description} token must have {allowed} parts (has {actual})"""


class BAD_INTEGER(UserError):
    """{description} must be an integer (got `{token}`)"""


class BAD_POSITIVE_INTEGER(UserError):
    """{description} must be a positive integer (got `{token}`)"""


class BAD_FIELD_SIZE(UserError):
    """{description} must be an integer multiple of 8 (got `{token}`)"""


class ILLEGAL_VALUE(MappingError):
    """`{key}` is not a valid value for {description}; must be one of {allowed}"""


class ILLEGAL_OPTIONAL_VALUE(MappingError):
    """`{key}` is not a valid value for {description}; must be one of {allowed} (or omitted)"""


class INVALID_HEXDUMP(UserError):
    """invalid hex dump for {description}"""


class BAD_ENCODING_NAME(UserError):
    """{description} `{name}` is not a valid string encoding"""


# Helper functions that read token parts from the iterator and
# yield parsed token parts. The `description` is partial'd on.
# Any uncaught StopIteration here is a bug; the token parts have been
# counted ahead of time and should be exactly sufficient.
def _string(description, it):
    return next(it)


def _optional_string(description, it):
    try:
        return next(it)
    except StopIteration:
        return None


def _int_helper(error, description, token):
    # FIXME UserError.convert can't do this.
    try:
        return int(token, 0)
    except ValueError as e:
        raise error(token=token, description=description) from e


def _integer(description, it):
    token = next(it)
    return _int_helper(BAD_INTEGER, description, token)


def _optional_integer(description, it):
    try:
        token = next(it)
    except StopIteration:
        token = ''
    return None if token == '' else _int_helper(BAD_INTEGER, description, token)


def _positive_integer(description, it):
    token = next(it)
    result = _int_helper(BAD_POSITIVE_INTEGER, description, token)
    BAD_POSITIVE_INTEGER.require(
        result > 0, token=token, description=description
    )
    return result


def _multiple_of_8(description, it):
    token = next(it)
    result = _int_helper(BAD_FIELD_SIZE, description, token)
    BAD_FIELD_SIZE.require(
        result % 8 == 0, token=token, description=description
    )
    return result


def _whitelisted_string(whitelist, description, it):
    try:
        token = next(it)
    except StopIteration:
        # This should only happen when the value is optional,
        # indicated by `None` being in the whitelist.
        token = None
    # Handle None separately when formatting any potential error.
    allowed = set(whitelist.keys())
    if None in allowed:
        allowed.discard(None)
        error = ILLEGAL_OPTIONAL_VALUE
    else:
        error = ILLEGAL_VALUE
    return error.get(whitelist, token, allowed=allowed, description=description)


def _hexdump(description, it):
    try:
        return binascii.unhexlify(''.join(next(it).split()))
    except binascii.Error as e:
        raise INVALID_HEXDUMP(description=description) from e


def _encoding(description, it):
    name = next(it)
    try:
        return codecs.lookup(name)
    except LookupError:
        raise BAD_ENCODING_NAME(description=description, name=name) from e


def _make_set(converter, it):
    return set(converter(iter((i,))) for i in it)


def _make_seq(converter, it):
    return tuple(converter(iter((i,))) for i in it)


# Main parsing machinery.
def _add(x, y):
    return None if (x is None or y is None) else x + y


def _check(low, high, name, token):
    actual = len(token)
    allowed = f'at least {low}' if high is None else f'{low}-{high}'
    WRONG_PART_COUNT.require(
        actual >= low,
        description=name, actual=actual, allowed=allowed
    )
    WRONG_PART_COUNT.require(
        high is None or actual <= high,
        description=name, actual=actual, allowed=allowed
    )


def _extract(converters, low, high, name, token):
    _check(low, high, name, token)
    it = iter(token) # must create ahead of time, so that it's reused
    # (the iterator tracks the state of parsing through the token)
    return tuple(converter(it) for converter in converters)


# Separate logic isn't strictly necessary, but it's simpler and faster.
def _extract_one(converter, low, high, name, token):
    _check(low, high, name, token)
    return converter(iter(token))


def _make_converter(spec, description):
    if isinstance(spec, (tuple, list, set)):
        return partial(
            _whitelisted_string, {x:x for x in spec}, description
        ), 1, 1
    if isinstance(spec, dict):
        return partial(
            _whitelisted_string, spec, description
        ), 0 if None in spec else 1, 1
    if spec.startswith('{'):
        return partial(
            _make_set, _make_converter(spec[1:], description)[0]
        ), 0, None
    if spec.startswith('['):
        return partial(
            _make_seq, _make_converter(spec[1:], description)[0]
        ), 0, None
    func, low, high = {
        'string': (_string, 1, 1),
        'string?': (_optional_string, 0, 1),
        'integer': (_integer, 1, 1),
        'integer?': (_optional_integer, 0, 1),
        'positive': (_positive_integer, 1, 1),
        'fieldsize': (_multiple_of_8, 1, 1),
        'hexdump': (_hexdump, 1, 1),
        'encoding': (_encoding, 1, 1)
    }[spec]
    return partial(func, description), low, high


def make_parser(name, *specs):
    converters, lows, highs = zip(*(
        _make_converter(spec, description)
        for spec, description in specs
    ))
    low = sum(lows)
    if None in highs: # it must be unique, and the last element.
        assert highs[-1] is None
        assert highs.count(None) == 1
        high = None
    else:
        high = sum(highs)
    return partial(_extract, converters, low, high, name)


def single_parser(name, spec):
    converter, low, high = _make_converter(spec, name)
    return partial(_extract_one, converter, low, high, name)
