from ..errors import MappingError, UserError
from .token_parsing import make_parser, single_parser
from ast import literal_eval
from functools import partial
import re, string, textwrap


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


class BAD_TOKEN_PART(UserError):
    """Can't represent `{text}` as part of a multipart token"""


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


# FIXME: hashes inside quotes
_tokenizer = re.compile('|'.join((
    r'(?:(?P<doublequoted>"(?:[^"\\]|\\.)*")\s*)',
    r"(?:(?P<singlequoted>'(?:[^'\\]|\\.)*')\s*)",
    r'(?:\[(?P<bracketed>[^\[\]]*)\]\s*)',
    r'(?:(?P<plain>[^\s\[\]]+)\s*)',
    r'(?P<unmatched>.)'
)))


def _literal(text):
    return [literal_eval(text)]


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
        'singlequoted': _literal,
    }[groupname](text)
    EMPTY_TOKEN.require(bool(token), position=position, line=line)
    return token


def tokenize(line):
    result = [_clean_token(match, line) for match in _tokenizer.finditer(line)]
    assert len(result) > 0 # empty lines should have been stripped.
    assert [] not in result # empty tokens should have raised an exception.
    return result


# Don't allow anything that could cause a problem:
# * control characters
# * whitespace (not allowed in single-word token)
# * quotes, square brackets, comma, colon (used for tokenization)
# * hash (used for file comments)
# * plus sign (used for line continuation)
_CLEAN_CHARS = set(string.printable) - set(string.whitespace) - set('\'"[]:,#+')


def _dirty(text):
    # Check for characters with special meaning for token interpretation.
    return not _CLEAN_CHARS.issuperset(set(text))


def _format_token(token):
    if len(token) == 1:
        t = token[0]
        # New: a single-part token with whitespace can't just be wrapped in
        # [] because the whitespace may be significant.
        return repr(t) if _dirty(t) else t
    for part in token:
        BAD_TOKEN_PART.require(not _dirty(part), text=part)
    return f"[{', '.join(token)}]"


# Used as the final step in producing output when disassembling.
def output_line(outfile, *tokens):
    tokens = list(map(_format_token, tokens))
    # FIXME: wrap the line when appropriate.
    # The textwrap module will unavoidably break quoted strings
    outfile.write(' '.join(tokens) + '\n')


# Parsing functionality used elsewhere.
def _parse_arguments(dispatch, tokens):
    result = {}
    for token in tokens:
        (name, handler), arguments = dispatch(token)
        DUPLICATE_PARAMETER.require(name not in result)
        result[name] = handler(arguments)
    return result


def argument_parser(**parameters):
    lookup = {
        # Each token can provide a single spec, that will be used
        # to re-parse the token parts after the label.
        name: (name, single_parser(f'`{name}` argument', spec))
        for name, spec in parameters.items()
    }
    parser = make_parser(
        'named argument',
        (lookup, 'argument name'),
        ('[string', 'argument data')
    )
    return partial(_parse_arguments, parser)


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
