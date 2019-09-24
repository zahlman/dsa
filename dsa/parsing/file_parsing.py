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
    """A Loader implementation that checks for a single level of indentation."""
    def line(self, indent, tokens):
        """Called repeatedly with lines of the data being loaded."""
        (self.indented if indent else self.unindented)(tokens)


    def result(self):
        """Do any deferred processing on the loaded data and return an object
        representing the result.
        The loader will not be used again after this call, so this method
        may destroy internal state or return a reference thereto."""
        raise NotImplemented


def feed(source_name, loader, lines):
    trace(f'Loading: {source_name}')
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
        with open(filename) as f:
            feed(f"File '{filename}'", loader.line, process(f))
    return loader.result()


def load_files_tagged(filenames, make_loader, *args, **kwargs):
    result = {}
    for filename in filenames:
        loader = make_loader(*args, **kwargs)
        label = os.path.splitext(os.path.basename(filename))[0]
        with open(filename) as f:
            feed(f"File '{filename}'", loader.line, process(f))
        DUPLICATE_FILE.add_unique(result, label, loader.result())
    return result
