from description import description_maker
from element import make_option, make_type
from field import field_maker 
from parse_config import process
from functools import partial
import os


def throw(line, e):
    raise ValueError('Line {line}: {e}')


def is_option_separator(line_tokens):
    return len(line_tokens) == 1 and all(c == '-' for c in line_tokens[0])


def load_template(filename):
    descriptions = []
    field_tokens = None
    field_doc = None
    fields = []
    options = []
    element_doc = []
    name = os.path.splitext(os.path.basename(filename))[0]
    with open(filename) as f:
        for position, indent, line_tokens, doc in process(f):
            if position == 0: # file doc.
                element_doc.extend(doc)
            elif is_option_separator(line_tokens):
                element_doc.extend(doc)
                # set up the last field of the option.
                if field_tokens is None:
                    throw(position, 'option must have at least one field')
                fields.append(field_maker(field_tokens, field_doc, descriptions))
                descriptions = []
                # make an option from the fields accumulated.
                options.append(partial(make_option, fields))
                fields = []
                field_tokens = None
                field_doc = None
            elif indent: # description.
                if field_tokens is None:
                    throw(position, 'description must be inside a field')
                descriptions.append(description_maker(line_tokens, doc))
            else: # start a new field.
                if field_tokens is not None:
                    fields.append(field_maker(field_tokens, field_doc, descriptions))
                descriptions = []
                field_tokens = line_tokens
                field_doc = doc
    # set up the last field of the last option.
    if field_tokens is None:
        throw(position, 'option must have at least one field')
    fields.append(field_maker(field_tokens, field_doc, descriptions))
    # make the last option.
    options.append(partial(make_option, fields))
    return partial(make_type, options, name, element_doc)
