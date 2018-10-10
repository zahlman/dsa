import errors
from functools import lru_cache, partial
import glob, os, re, textwrap


class NOT_ENOUGH_PARTS(errors.UserError):
    """not enough parts for multipart token"""


class TOO_MANY_PARTS(errors.UserError):
    """too many parts for multipart token"""


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


def process(lines):
    position, indent, line = 0, '', ''
    for i, raw_line in enumerate(lines, 1):
        raw_line, mark, comment = raw_line.partition('#')
        raw_line = raw_line.rstrip()
        if not raw_line:
            continue
        contents = raw_line.lstrip()
        raw_indent = raw_line[:-len(contents)]
        if contents.startswith('+'):
            line += contents[1:]
            continue
        # If we get here, we have a new "real" line.
        # As long as we weren't at the start of the file, yield the old line.
        if line:
            yield position, indent, tokenize(line)
        else:
            assert position == 0
        position, indent, line = i, raw_indent, raw_line
    # At EOF, yield the final chunk.
    yield position, indent, tokenize(line)


def glob_files(patterns, base):
    for pattern in patterns:
        for filename in glob.glob(os.path.join(base, pattern), recursive=True):
            yield os.path.abspath(filename)


def resolve_filenames(lib_globs, usr_globs):
    yield from glob_files(lib_globs, os.path.split(__file__)[0])
    yield from glob_files(usr_globs, os.getcwd())


def feed(source_name, label, accumulator, machine, lines):
    print("Loading:", source_name)
    for position, indent, line_tokens in lines:
        errors.wrap(
            f'{source_name}: Line', position,
            machine.add_line, indent, line_tokens
        )
    machine.end_file(label, accumulator)


def feed_file(machine, accumulator, filename):
    label = os.path.splitext(os.path.basename(filename))[0]
    with open(filename) as f:
        feed(f"File '{filename}'", label, accumulator, machine, process(f))


def load_globs(machine, lib_globs, usr_globs):
    accumulator = {}
    for filename in resolve_filenames(lib_globs, usr_globs):
        feed_file(machine, accumulator, filename)
    return accumulator


def load_file(machine, filename):
    accumulator = {}
    feed_file(machine, accumulator, filename)
    return accumulator


# Interface for testing.
def load_lines(machine, lines):
    accumulator = {}
    feed("String data", None, accumulator, machine, lines)
    return accumulator
