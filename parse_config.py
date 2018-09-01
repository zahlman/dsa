import re


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


def process(lines):
    position, indent, line, doc = 0, '', '', []
    for i, raw_line in enumerate(lines, 1):
        if raw_line.startswith('##'):
            doc.append(raw_line[2:].strip())
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
