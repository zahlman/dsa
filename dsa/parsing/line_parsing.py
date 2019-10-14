from ..errors import MappingError, UserError
from .token_parsing import make_parser, single_parser
from ast import literal_eval
from functools import partial
import re, string, textwrap


class BAD_TOKEN(UserError):
    """Character {position}: bad token (or unmatched quote/bracket) `{text}`
    {line}
    {space}{underline}"""


class MISSING_WHITESPACE(UserError):
    """Character {position}: missing whitespace between tokens
    {line}
    {space}{underline}"""


class BAD_TOKEN_PART(UserError):
    """Can't represent `{text}` as part of a multipart token"""


class DUPLICATE_PARAMETER(MappingError):
    """duplicate specification of parameter `{key}`"""


class UNRECOGNIZED_PARAMETER(MappingError):
    """unrecognized parameter `{key}`"""


class MISSING_PARAMETERS(UserError):
    """missing required parameters `{missing}`"""


class BAD_LINE(UserError):
    """`{description}` line should have {expected} tokens (has {actual})"""


def token_splitter(delims):
    # Also used by description.FlagsDescription to parse `|`s.
    return re.compile(f'\s*[{re.escape(delims)}]\s*').split


_split = token_splitter(':,')


# FIXME: hashes inside quotes
_tokenizer = re.compile('|'.join((
    r'(?P<comment>#.*)',
    r'(?P<whitespace>\s+)',
    r'(?P<doublequoted>"(?:[^\\"]|\\.)*")',
    r"(?P<singlequoted>'(?:[^\\']|\\.)*')",
    # Bracketed token may contain quotes but not a comment char or at-sign
    # (except in front of the brackets).
    r'(?P<bracketed>@?\[[^@#\[\]]*\])',
    # Single-word token can't contain quotes either.
    r'(?P<plain>@?[^@#\'"\s\[\]]+)',
    # These error tokens are used to highlight multiple characters
    # when the error is reported.
    r'(?P<bad_bracket>@?\[[^@#\[\]]*(?=[@#\[]))',
    r'(?P<empty_label>@)(?=[@#\'"\s\]])',
    # Failsafe: match any single char (including unmatched quotes).
    r'(?P<unmatched>.)'
)))


_linestart = re.compile('^[+!\s]?')


_have_whitespace = True


def _require_whitespace(position, line):
    global _have_whitespace
    MISSING_WHITESPACE.require(
        _have_whitespace,
        position=position, line=line.rstrip(),
        space=' '*position, underline='^'
    )
    _have_whitespace = False


def _error(text, position, line):
    raise BAD_TOKEN(
        position=position, text=text, line=line.rstrip(),
        space=' '*position, underline='^'*len(text)
    )


def _ignore(text, position, line):
    global _have_whitespace
    _have_whitespace = True
    return
    yield # a generator, but without yielding anything.


def _literal(text, position, line):
    _require_whitespace(position, line)
    yield [literal_eval(text)]


def _multipart(text, position, line):
    _require_whitespace(position, line)
    prefix, text = (['@'], text[1:]) if text.startswith('@') else ([], text)
    text = text[1:-1] if text.startswith('[') else text
    yield prefix + _split(' '.join(text.split()))


def _clean_tokens(line):
    for match in _tokenizer.finditer(line):
        groupname = match.lastgroup
        text = match.group(groupname)
        position = match.start()
        yield from {
            'comment': _ignore,
            'whitespace': _ignore,
            'doublequoted': _literal,
            'singlequoted': _literal,
            'bracketed': _multipart,
            'plain': _multipart,
            'bad_bracket': _error,
            'empty_label': _error,
            'unmatched': _error
        }[groupname](text, position, line)


def tokenize(line):
    global _have_whitespace
    _have_whitespace = True # reset from previous line
    # Always generate a special token at the start of the line, and
    # include the first character if it's special.
    prefix = _linestart.match(line).group()
    return prefix, list(_clean_tokens(line[len(prefix):]))


_SPECIAL = { # characters that can cause problems inside non-Quoted tokens.
    '[', ']', # used to wrap multipart tokens
    ':', ',', # used to separate parts
    '#' # comments
    # line continuations (+) don't cause a problem because they won't be at
    # the start of a line. But they must be wrapped to ensure that.
}
# Quotes and whitespace are allowed, but the token will be wrapped
# and whitespace normalized when parsed back.
_CLEAN = (set(string.printable) - _SPECIAL).issuperset
_NEEDS_WRAPPING = {' ', "'", '"', '+'}.intersection


class _Token:
    def __getitem__(self, index):
        if index != 0:
            raise IndexError
        return str(self)


    def __len__(self):
        return 1


    def __repr__(self):
        return f'{self.__class__.__name__}({str(self)})'


class Quoted(_Token):
    def __init__(self, text):
        self._text = text


    def __str__(self):
        return repr(self._text)


class Comment(_Token):
    def __init__(self, text):
        self._text = text


    def __str__(self):
        return f'# {self._text}'


def _format_token(token, compact):
    if isinstance(token, _Token):
        return str(token)
    # single-part and multipart tokens
    if not token:
        # need special handling; wouldn't be detected as needing wrapping
        return '[]'
    prefix, token = ('@', token[1:]) if token[0] == '@' else ('', token)
    for part in token:
        BAD_TOKEN_PART.require(_CLEAN(part), text=part)
    joined = (':' if compact else ', ').join(token)
    return prefix + (f'[{joined}]' if _NEEDS_WRAPPING(joined) else joined)


# Used as the final step in producing output when disassembling.
def output_line(outfile, prefix, *tokens, compact=False):
    tokens = [_format_token(token, compact) for token in tokens]
    # FIXME: wrap the line when appropriate.
    # The textwrap module will unavoidably break quoted strings
    outfile.write(prefix + ' '.join(tokens) + '\n')


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
