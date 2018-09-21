from description import description_maker
from field import field_maker
from member import member_maker
from parse_config import cached_loader


def is_option_separator(line_tokens):
    return len(line_tokens) == 1 and all(c == '-' for c in line_tokens[0])


class TypeDescriptionLSM:
    def __init__(self):
        self._reset_field_data()
        self.member_doc = []
        self.field_makers = [[]] # list of lists, one for each Option.
        self.deferral = {}


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


    def add_line(self, position, indent, line_tokens, doc):
        if position == 0:
            self.add_doc(doc)
        elif is_option_separator(line_tokens):
            self.add_doc(doc)
            self.next_option()
        elif indent:
            self.push_description(line_tokens, doc)
        else:
            self.start_field(line_tokens, doc)


    def result(self, name):
        self._finish_option()
        return member_maker(
            name, self.field_makers, self.member_doc
        ), self.deferral


load = cached_loader(TypeDescriptionLSM)
