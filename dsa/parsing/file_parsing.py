from ..ui.tracing import trace
from ..errors import wrap as wrap_errors, MappingError
from .line_parsing import tokenize
from copy import deepcopy
import os.path


class DUPLICATE_FILE(MappingError):
    """Filenames must be unique"""


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
            # TODO: allow custom tokenization.
            yield position, indent, tokenize(line)
        else:
            assert position == 0
        position, indent, line = i, raw_indent, contents
    # At EOF, yield the final chunk.
    yield position, indent, tokenize(line)


class SimpleLoader:
    """A Loader implementation that checks for a single level of indentation
    and creates its accumulator by cloning."""
    @classmethod
    def create_with_accumulator(cls, *args, **kwargs):
        return cls(*args, **kwargs), deepcopy(cls.__accumulator__)


    def __call__(self, accumulator, indent, tokens):
        (self.indented if indent else self.unindented)(accumulator, tokens)


def feed(source_name, loader, accumulator, lines):
    trace(f'Loading: {source_name}')
    for position, indent, line_tokens in lines:
        wrap_errors(
            f'{source_name}: Line {position}',
            loader, accumulator, indent, line_tokens
        )


def load_lines(lines, make_loader, *args, **kwargs):
    loader, accumulator = make_loader(*args, **kwargs)
    feed("String data", loader, accumulator, process(lines))
    return accumulator


def load_files(filenames, make_loader, *args, **kwargs):
    loader, accumulator = make_loader(*args, **kwargs)
    for filename in filenames:
        with open(filename) as f:
            feed(f"File '{filename}'", loader, accumulator, process(f))
    return accumulator


def load_files_tagged(filenames, make_loader, *args, **kwargs):
    result = {}
    for filename in filenames:
        loader, accumulator = make_loader(*args, **kwargs)
        label = os.path.splitext(os.path.basename(filename))[0]
        with open(filename) as f:
            feed(f"File '{filename}'", loader, accumulator, process(f))
        DUPLICATE_FILE.add_unique(result, label, accumulator)
    return result 
