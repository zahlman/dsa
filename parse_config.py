from functools import lru_cache, partial
import os, re, textwrap


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


def parts_of(token, separator, required, allowed, last_list):
    parts = [
        x.strip() if x.strip() else None
        for x in token.split(separator)
    ]
    count = len(parts)
    if count < required:
        raise ValueError('not enough parts for multipart token')
    elif count < allowed:
        padding = allowed - count - (1 if last_list else 0)
        parts.extend([None] * padding)
    if last_list: # group up the last token, even if padding occurred.
        parts = parts[:allowed-1] + [parts[allowed-1:]]
    elif count > allowed:
        raise ValueError('too many parts for multipart token')
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
    position, indent, line, doc = 0, '', '', []
    for i, raw_line in enumerate(lines, 1):
        if raw_line.strip().startswith('##'):
            doc.append(raw_line.strip()[2:].strip())
            continue
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
        yield position, indent, tokenize(line), doc
        position, indent, line, doc = i, raw_indent, raw_line, []
    # At EOF, yield the final chunk.
    yield position, indent, tokenize(line), doc


def get_file(paths, name):
    for folder in paths:
        try:
            filename = os.path.join(folder, f'{name}.txt')
            with open(filename) as f:
                return list(process(f))
        except FileNotFoundError: # local open() failed; try another path.
            continue
    raise FileNotFoundError(f'no valid path contained {name}.txt')


def library(paths):
    return lru_cache(None)(partial(get_file, paths))


# Separating this out allows for testing from hard-coded `lines`.
def create(new_state_machine, lines, name):
    machine = new_state_machine()
    for position, indent, line_tokens, doc in lines:
        try:
            machine.add_line(position, indent, line_tokens, doc)
        except ValueError as e:
            raise ValueError(f'Line {position}: {e}')
    return machine.result(name)


def load(new_state_machine, get_file, name):
    return create(new_state_machine, get_file(name), name)


# While it's true that the underlying file could change between calls, we would
# actually prefer to ignore such changes.
def cached_loader(new_state_machine, paths):
    return lru_cache(None)(partial(load, new_state_machine, library(paths)))
