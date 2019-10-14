from .errors import UserError
from string import printable as printable_chars


class BAD_TOKEN_PART(UserError):
    """Can't represent `{text}` as part of a multipart token"""


_SPECIAL = { # characters that can cause problems inside non-Quoted tokens.
    '[', ']', # used to wrap multipart tokens
    ':', ',', # used to separate parts
    '#' # comments
    # line continuations (+) don't cause a problem because they won't be at
    # the start of a line. But they must be wrapped to ensure that.
}
# Quotes and whitespace are allowed, but the token will be wrapped
# and whitespace normalized when parsed back.
_CLEAN = (set(printable_chars) - _SPECIAL).issuperset
_NEEDS_WRAPPING = {' ', "'", '"', '+'}.intersection


def _format_token(token, compact):
    if not token:
        # need special handling; wouldn't be detected as needing wrapping
        return '[]'
    first, *rest = token
    if first.startswith(('"', "'", '#')):
        # quoted strings and comments must not be joined or wrapped.
        assert not rest
        return first
    prefix, token = ('@', rest) if first == '@' else ('', token)
    for part in token:
        BAD_TOKEN_PART.require(_CLEAN(part), text=part)
    joined = (':' if compact else ', ').join(token)
    assert joined == ' '.join(joined.split())
    return prefix + (f'[{joined}]' if _NEEDS_WRAPPING(joined) else joined)


_MAX_LINE_LENGTH = 78
_CONTINUATION = '\n+   '


def _output_line_tokens(outfile, first, rest, position, compact=False):
    formatted = _format_token(first, compact)
    outfile.write(formatted) # even if it "doesn't fit"
    position += len(formatted)
    for token in rest:
        formatted = _format_token(token, compact)
        output = ' ' + formatted
        position += len(output)
        if position > _MAX_LINE_LENGTH:
            # If we line-wrapped a comment onto the next line, just use
            # a full-line comment.
            prefix = '' if formatted.startswith('#') else _CONTINUATION
            output = prefix + formatted
            position = len(output)
        outfile.write(output)


def _output_line(outfile, prefix, *tokens, compact=False):
    assert isinstance(prefix, str) and prefix.strip() in {'+', '!', ''}
    outfile.write(prefix)
    if tokens:
        first, *rest = tokens
        _output_line_tokens(outfile, first, rest, len(prefix), compact)
    outfile.write('\n')


def output_file(filename, lines, compact=False):
    """Write a DSA file (type/structgroup/data definition or path file).

    `filename` -> path to output file
    `lines` -> iterable of line iterables; each line contains a string
    "prefix" followed by zero or more iterable-of-string "tokens".
    The prefix must either be '+', '!' or whitespace (possibly empty).
    `compact` -> if true, use ':' to join multi-part tokens instead of ', '
    """
    with open(filename, 'w') as f:
        for line in lines:
            _output_line(f, *line, compact=compact)
