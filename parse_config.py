import re
from functools import partial


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


def deferred_parameter(name, value_parser, deferred):
    try:
        return value_parser(deferred[name])
    except KeyError:
        raise ValueError(f'template parameter <{name}>: missing value')
    except ValueError as e:
        raise ValueError(f'template parameter <{name}>: {e}')


def constant(value, deferred):
    return value


def parse_wrapper(func):
    def wrapped(text):
        if text.startswith('<') and text.endswith('>'):
            return partial(deferred_parameter, text[1:-1], func)
        else:
            return partial(constant, func(text))
    return wrapped


def parse_int_raw(text):
    return int(text, 0)


parse_int = parse_wrapper(parse_int_raw)


def parse_base_raw(text):
    try:
        return {'2': bin, '8': oct, '10': str, '16': hex}[text]
    except KeyError:
        raise ValueError(
            "invalid base setting (must be one of '2', '8', '10' or '16')"
        )


parse_base = parse_wrapper(parse_base_raw)
    

def parse_bool_raw(text):
    if text.lower() == 'true':
        return True
    if text.lower() == 'false':
        return False
    return bool(int(text, 0))


parse_bool = parse_wrapper(parse_bool_raw)


def parse_deferred(text):
    # Used for forwarding template parameters.
    return text


def get_flag_value(items, value_parser):
    if len(items) == 1:
        return value_parser(items[0])
    if len(items) == 0 and value_parser is parse_bool:
        return partial(constant, True)
    raise ValueError('invalid flag value')


def parse_flags(flag_tokens, whitelist):
    result = {
        name: partial(constant, default) 
        for name, (value_parser, default) in whitelist.items()
    }
    specified = set()
    for token in flag_tokens:
        name, *items = [x.strip() for x in token.split(':')]
        if name in specified:
            raise ValueError(f"duplicate entry for flag '{name}'")
        specified.add(name)
        try:
            value_parser, default = whitelist[name]
        except KeyError:
            raise ValueError(f"unrecognized flag '{name}'")
        result[name] = get_flag_value(items, value_parser)

    return result


def fill_template(template, deferred):
    return {k: v(deferred) for k, v in template.items()}
