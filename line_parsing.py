import errors
import binascii
from functools import partial
import re, textwrap


class TokenError(errors.UserError):
    # Represents an error in the number of tokens on a line or the number of
    # parts of a token.
    @classmethod
    def pad(cls, token, required, total, **kwargs):
        actual = len(token)
        if required <= actual <= total:
            return token + ([None] * (total - actual))
        raise cls(actual=actual, **kwargs)


class LineError(errors.UserError):
    def __init__(self, **kwargs):
        space = ' ' * kwargs['position']
        super().__init__(space=space, **kwargs)


class UNMATCHED_BRACKET(LineError):
    """Character {position}: unmatched `{bracket}`
    {line}
    {space}^
    (N.B. brackets may not be nested)"""


class EMPTY_TOKEN(LineError):
    """Character {position}: empty token
    {line}
    {space}^
    (N.B. use `0` for empty sets of flags)"""


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


def _normalize(token):
    return ' '.join(token.split())


def token_splitter(delims):
    # Also used by description.FlagsDescription to parse `|`s.
    return re.compile(f'\s*[{re.escape(delims)}]\s*').split


_split = token_splitter(':,')


_tokenizer = re.compile('|'.join((
    r'(?:(?P<plain>[^\s\[\]]+)\s*)',
    r'(?:\[(?P<bracketed>[^\[\]]*)\]\s*)',
    r'(?P<unmatched>.)'
)))


def _token_gen(line):
    # Leading whitespace was handled in file_parsing.
    for match in _tokenizer.finditer(line):
        # Exactly one group should match.
        groupname = match.lastgroup
        text = match.group(groupname)
        position = match.start()
        UNMATCHED_BRACKET.require(
            groupname != 'unmatched',
            position=position, bracket=text, line=line
        )
        text = _normalize(text)
        EMPTY_TOKEN.require(bool(text), position=position, line=line)
        yield _split(text)


def tokenize(line):
    result = list(_token_gen(line))
    assert len(result) > 0 # empty lines should have been stripped.
    assert [] not in result # empty tokens should have raised an exception.
    return result


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
        name, *item = token
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
