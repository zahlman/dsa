from ..errors import MappingError, UserError
from .token_parsing import make_parser, single_parser
from functools import partial
import re, textwrap


class TokenError(UserError):
    """Represents an error in the number of tokens on a line or the number of
    parts of a token."""


    @classmethod
    def pad(cls, token, required, total, **kwargs):
        """Helper for verifying and sanitizing the number of components."""
        actual = len(token)
        if required <= actual <= total:
            return token + ([[]] * (total - actual))
        raise cls(actual=actual, **kwargs)


    # Used either to take a token from the front of a line
    # or a token part from the front of a token.
    @classmethod
    def shift(cls, tokens, **kwargs):
        try:
            first, *rest = tokens
            return first, rest
        except ValueError:
            raise cls(**kwargs)


class LineError(UserError):
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


class DUPLICATE_PARAMETER(MappingError):
    """duplicate specification of parameter `{key}`"""


class UNRECOGNIZED_PARAMETER(MappingError):
    """unrecognized parameter `{key}`"""


class MISSING_PARAMETERS(UserError):
    """missing required parameters `{missing}`"""


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
