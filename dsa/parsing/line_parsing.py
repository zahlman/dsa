from ..errors import MappingError, UserError
from .token_parsing import make_parser, single_parser
from functools import partial
import re, textwrap


class LineError(UserError):
    def __init__(self, **kwargs):
        space = ' ' * kwargs['position']
        super().__init__(space=space, **kwargs)


class UNMATCHED_BRACKET_OR_QUOTE(LineError):
    """Character {position}: unmatched `{bracket}`
    {line}
    {space}^
    (N.B. brackets may not be nested)"""


class EMPTY_TOKEN(LineError):
    """Character {position}: empty token
    {line}
    {space}^
    (N.B. use `0` for empty sets of flags)"""


class DUPLICATE_PARAMETER(MappingError):
    """duplicate specification of parameter `{key}`"""


class UNRECOGNIZED_PARAMETER(MappingError):
    """unrecognized parameter `{key}`"""


class MISSING_PARAMETERS(UserError):
    """missing required parameters `{missing}`"""


class BAD_LINE(UserError):
    """{description} line should have {expected} tokens (has {actual})"""


def token_splitter(delims):
    # Also used by description.FlagsDescription to parse `|`s.
    return re.compile(f'\s*[{re.escape(delims)}]\s*').split


_split = token_splitter(':,')


_tokenizer = re.compile('|'.join((
    r'(?:"(?P<doublequoted>(?:[^"\\]|\\.)*)"\s*)',
    r"(?:'(?P<singlequoted>(?:[^'\\]|\\.)*)'\s*)",
    r'(?:\[(?P<bracketed>[^\[\]]*)\]\s*)',
    r'(?:(?P<plain>[^\s\[\]]+)\s*)',
    r'(?P<unmatched>.)'
)))


def _literal(text):
    return [text]


def _multipart(text):
    return _split(' '.join(text.split()))


def _clean_token(match, line):
    # Leading whitespace was handled in file_parsing.
    # Exactly one group should match.
    groupname = match.lastgroup
    text = match.group(groupname)
    position = match.start()
    UNMATCHED_BRACKET_OR_QUOTE.require(
        groupname != 'unmatched',
        position=position, bracket=text, line=line
    )
    token = {
        'plain': _multipart,
        'bracketed': _multipart,
        'doublequoted': _literal,
        'singlequoted': _literal
    }[groupname](text)
    EMPTY_TOKEN.require(bool(token), position=position, line=line)
    return token


def tokenize(line):
    result = [_clean_token(match, line) for match in _tokenizer.finditer(line)]
    assert len(result) > 0 # empty lines should have been stripped.
    assert [] not in result # empty tokens should have raised an exception.
    return result


def wrap_multiword(token):
    return token if token == ''.join(token.split()) else f'[{token}]'


# Used as the final step in producing output when disassembling.
def format_line(tokens):
    tokens = list(map(wrap_multiword, tokens))
    return textwrap.wrap(
        ' '.join(tokens), width=78,
        # Indicate the wrapped lines according to spec.
        subsequent_indent=' ' * len(tokens[0]) + ' + ',
        # Ensure that `textwrap` doesn't alter anything important.
        break_long_words=False, break_on_hyphens=False
    )


# Parsing functionality used elsewhere.
class Namespace:
    def __init__(self, items):
        for key, value in items.items():
            setattr(self, key, value)


def _parse_arguments(expected, defaults, dispatch, tokens):
    result = defaults.copy() # in case the parser is reused.
    seen = set()
    for token in tokens:
        d = dispatch(token)
        (name, handler), arguments = d
        DUPLICATE_PARAMETER.require(name not in seen)
        seen.add(name)
        result[name] = handler(arguments)
    missing = expected - set(result.keys())
    MISSING_PARAMETERS.require(not missing, missing=missing)
    return Namespace(result)


def argument_parser(defaults, **parameters):
    lookup = {
        # Each token can provide a single spec, that will be used
        # to re-parse the token parts after the label.
        name: (name, single_parser(f'`{name}` argument', spec))
        for name, spec in parameters.items()
    }
    # We make a parser that reads the label and the rest of the tokens,
    # converting the label into another parser that handles the rest.
    # Finally we set up code that will invoke the parser and merge its
    # results with the `defaults`.
    return partial(_parse_arguments,
        set(parameters.keys()), defaults,
        make_parser(
            'named argument',
            (lookup, 'argument name'),
            ('[string', 'argument data')
        )
    )


def _extract_gen(more, parsers, line):
    for parser, token in zip(parsers, line):
        yield parser(token)
    if len(parsers) > len(line):
        for p in parsers[len(line):]:
            yield p(())
    if more:
        # we yield an empty sequence when there isn't an excess.
        yield line[len(parsers):]


def _extract_tokens(description, extracted, required, more, parsers, line):
    assert required <= len(parsers)
    actual = len(line) + extracted
    low = required + extracted
    high = len(parsers) + extracted
    expected = f'at least {low}' if more else f'exactly {low}' if low == high else f'{low}-{high}'
    BAD_LINE.require(
        (actual >= low) and ((actual <= high) or more),
        description=description, expected=expected, actual=actual
    )
    return tuple(_extract_gen(more, parsers, line))


def line_parser(description, *parsers, extracted=0, required=0, more=False):
    """Create a parser for the first several tokens of a line.
    description: used for crafting error messages.
    extracted: number of previously extracted tokens, for error reporting.
    required: proxy tokens are used if there are more than this many `parsers`.
    more: if true, additional tokens are captured in a tuple
    (otherwise an error is reported for any additional tokens).
    parsers: output contains one item per parser (plus one if `more`)."""
    return partial(
        _extract_tokens, description, extracted, required, more, parsers
    )
