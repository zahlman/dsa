from arguments import Arguments
from description import description_maker
from field import field_maker 
from member import member_maker
from parse_config import process
from functools import lru_cache
from os.path import basename, splitext


class TemplateLoadingState:
    def __init__(self):
        self._reset_field_data()
        self.member_doc = []
        self.field_makers = [[]] # list of lists, one for each Option.
        self.deferral = Arguments({}, {})


    def _reset_field_data(self):
        self.description_makers = []
        self.field_tokens = None
        self.field_doc = None


    def _finish_field(self):
        self.field_makers[-1].append(field_maker(
            self.field_tokens, self.field_doc,
            self.description_makers, self.deferral
        ))
        self._reset_field_data()


    def _finish_option(self):
        if self.field_tokens is None:
            raise ValueError('option must have at least one field')
        self._finish_field()
        assert self.field_makers[-1]


    def add_doc(self, doc):
        self.member_doc.extend(doc)


    def push_description(self, line_tokens, doc):
        if self.field_tokens is None:
            raise ValueError('description must be inside a field')
        self.description_makers.append(description_maker(line_tokens, doc))


    def start_field(self, line_tokens, doc):
        if self.field_tokens is not None:
            self._finish_field()
        self.field_tokens = line_tokens
        self.field_doc = doc


    def next_option(self):
        self._finish_option()
        self.field_makers.append([])


    def complete(self):
        self._finish_option()
        return self.deferral, self.field_makers, self.member_doc


def throw(line, e):
    raise ValueError('Line {line}: {e}')


def is_option_separator(line_tokens):
    return len(line_tokens) == 1 and all(c == '-' for c in line_tokens[0])


# Separating this out is better for testing purposes, as we can create a
# temporary template from a list of strings without file I/O.
def create(name, lines):
    state = TemplateLoadingState()
    for position, indent, line_tokens, doc in process(lines):
        if position == 0:
            state.add_doc(doc)
        elif is_option_separator(line_tokens):
            state.add_doc(doc)
            state.next_option()
        elif indent:
            state.push_description(line_tokens, doc)
        else:
            state.start_field(line_tokens, doc)
    deferral, field_makers, member_doc = state.complete()
    return member_maker(name, field_makers, member_doc), deferral


# While it's true that the underlying file could change between calls, we would
# actually prefer to ignore such changes. This ensures a consistent definition
# for Members declared with the same type.
@lru_cache(None)
def load(filename):
    name = splitext(basename(filename))[0]
    with open(filename) as f:
        return create(name, f)
