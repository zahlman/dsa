from ..ui.tracing import trace
from ..errors import wrap as wrap_errors, MappingError
from .line_parsing import tokenize
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


def feed(source_name, label, accumulator, machine, lines):
    trace(f'Loading: {source_name}')
    for position, indent, line_tokens in lines:
        wrap_errors(
            f'{source_name}: Line {position}',
            machine.add_line, indent, line_tokens
        )
    machine.end_file(label, accumulator)


def feed_file(machine, accumulator, filename):
    label = os.path.splitext(os.path.basename(filename))[0]
    with open(filename) as f:
        feed(f"File '{filename}'", label, accumulator, machine, process(f))


def load_files(machine, *filenames):
    accumulator = {}
    for filename in filenames:
        feed_file(machine, accumulator, filename)
    return accumulator


def load_lines(machine, lines):
    accumulator = {}
    feed("String data", None, accumulator, machine, process(lines))
    return accumulator


# New interface.


def feed_new(source_name, loader, accumulator, lines):
    trace(f'Loading: {source_name}')
    for position, indent, line_tokens in lines:
        wrap_errors(
            f'{source_name}: Line {position}',
            loader, accumulator, indent, line_tokens
        )


def load_lines_new(lines, make_loader, *args, **kwargs):
    loader, accumulator = make_loader(*args, **kwargs)
    feed_new("String data", loader, accumulator, process(lines))
    return accumulator


def load_files_new(filenames, make_loader, *args, **kwargs):
    loader, accumulator = make_loader(*args, **kwargs)
    for filename in filenames:
        with open(filename) as f:
            feed_new(f"File '{filename}'", loader, accumulator, process(f))
    return accumulator


def load_files_tagged(filenames, make_loader, *args, **kwargs):
    result = {}
    for filename in filenames:
        loader, accumulator = make_loader(*args, **kwargs)
        label = os.path.splitext(os.path.basename(filename))[0]
        with open(filename) as f:
            feed_new(f"File '{filename}'", loader, accumulator, process(f))
        DUPLICATE_FILE.add_unique(result, label, accumulator)
    return result 
