from . import errors
from .line_parsing import tokenize
from functools import lru_cache, partial
import glob, os


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
        position, indent, line = i, raw_indent, contents
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


# Interface for testing.
def load_lines(machine, lines):
    accumulator = {}
    feed("String data", None, accumulator, machine, lines)
    return accumulator
