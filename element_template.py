from description import description_maker
from element import make_option, make_type
from field import FieldBuilder
from parse_config import process
from functools import partial
import os


def throw(line, e):
    raise ValueError('Line {line}: {e}')


def is_option_separator(line_tokens):
    return len(line_tokens) == 1 and all(c == '-' for c in line_tokens[0])


def load_template(filename):
    current_fields = []
    options = []
    all_doc = []
    name = os.path.splitext(os.path.basename(filename))[0]
    with open(filename) as f:
        for position, indent, line_tokens, doc in process(f):
            if position == 0: # file doc.
                all_doc.extend(doc)
            elif is_option_separator(line_tokens):
                all_doc.extend(doc)
                # make an option from the fields accumulated.
                if not current_fields:
                    throw(position, 'option must have at least one field')
                options.append(partial(make_option, current_fields))
                current_fields = []
            elif indent: # description.
                if not current_fields:
                    throw(position, 'description must be inside a field')
                current_fields[-1].add_description(
                    description_maker(line_tokens, doc)
                )
            else: # start a new field.
                current_fields.append(FieldBuilder(line_tokens, doc))
    # Make the last option.
    if not current_fields:
        throw(position, 'option must have at least one field')
    options.append(partial(make_option, current_fields))
    return partial(make_type, options, name, doc)
