# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

from .line_parsing import tokenize
from ..errors import wrap as wrap_errors, MappingError
from ..ui.tracing import my_tracer
import os.path


class DUPLICATE_FILE(MappingError):
    """Filenames must be unique"""


def process(lines):
    # New approach: tokenization handles comments and detection of
    # line continuation and indent tokens; here we just collate lines.
    # N.B. It now is not allowed to line-wrap in the middle of a token.
    # Also, we don't just detect indented tokens, but ones starting with '!'.
    line_number, marker, old_tokens = 0, '', []
    for i, line in enumerate(lines, 1):
        start, tokens = tokenize(line)
        if start == '+': # line continuation.
            old_tokens.extend(tokens)
        # Lines are considered "blank" if they have no tokens and also
        # aren't meta (prefixed with '!').
        elif (start == '!') or bool(tokens):
            # If there was a previous line to output, output it.
            if (marker == '!') or bool(old_tokens):
                yield line_number, marker, old_tokens
            line_number, marker, old_tokens = i, start, list(tokens)
    if (marker == '!') or bool(old_tokens): # dump the last line
        yield line_number, marker, old_tokens


class SimpleLoader:
    def line(self, indent, tokens):
        """Called repeatedly with lines of the data being loaded."""
        # Derived classes implement these handlers, as well as a `result`
        # method to do any deferred processing on the loaded data.
        # The `result` method may be destructive or return class internals
        # since the loader will not be used again after that point.
        if indent == '!':
            self.meta(tokens)
        elif indent:
            self.indented(tokens)
        else:
            self.unindented(tokens)


def feed(source_name, loader, lines):
    my_tracer.trace(f'Loading: {source_name}')
    for position, indent, line_tokens in lines:
        wrap_errors(
            f'{source_name}: Line {position}',
            loader, indent, line_tokens
        )


def load_lines(lines, make_loader, *args, **kwargs):
    loader = make_loader(*args, **kwargs)
    feed("String data", loader.line, process(lines))
    return loader.result()


def load_files(filenames, make_loader, *args, **kwargs):
    loader = make_loader(*args, **kwargs)
    for filename in filenames:
        with open(filename, encoding='utf-8') as f:
            feed(f'File `{filename}`', loader.line, process(f))
    return loader.result()


def load_files_into(result, filenames, make_loader, *args, **kwargs):
    for filename in filenames:
        loader = make_loader(*args, **kwargs)
        label = os.path.splitext(os.path.basename(filename))[0]
        with open(filename, encoding='utf-8') as f:
            feed(f'File `{filename}`', loader.line, process(f))
        DUPLICATE_FILE.add_unique(result, label, loader.result())


def load_files_tagged(filenames, make_loader, *args, **kwargs):
    result = {}
    load_files_into(filenames, make_loader, *args, **kwargs)
    return result
