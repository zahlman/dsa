from parse_config import process, parse_flags, fill_template
from parse_config import parse_int, parse_base, parse_bool
from type_parsers import FlagsDescription, RangeDescription, LabelledRangeDescription, RawField, Field, Option, Type
from functools import partial
import os


def is_number_or_blank(text):
    if not text:
        return True
    try:
        int(text, 0)
        return True
    except ValueError:
        return False


def get_value_range(items, minimum, maximum):
    count = len(items)
    if count > 2:
        raise ValueError('Too many parameters for range description')
    elif count == 2:
        low = int(items[0], 0) if items[0] else minimum
        high = int(items[1], 0) if items[1] else maximum
    else:
        # can't be empty here; if there was a label, it would have been
        # parsed as a flag name, and otherwise the line would be empty.
        assert count == 1
        if not items[0]:
            # This only happens for a LabelledRangeDescription;
            # otherwise, the whole line would be empty.
            raise ValueError('No range given for labelled range description')
        low = int(items[0], 0)
        high = int(items[0], 0)
    return low, high


def make_description_maker(line_tokens, doc):
    if len(line_tokens) != 1:
        raise ValueError('field description must be a single token')
    items = [t.strip() for t in line_tokens[0].split(':')]
    if not any(is_number_or_blank(i) for i in items):
        return partial(make_description, None, items, None, doc)
    elif is_number_or_blank(items[0]):
        # name = None
        return partial(make_description, None, None, items, doc)
    else:
        name, *items = items
        return partial(make_description, name, None, items, doc)


def make_description(
    name, flag_items, range_items, doc, minimum, maximum, bits, formatter
):
    if flag_items is not None:
        if len(flag_items) != bits:
            raise ValueError(
                f'expected {bits} flags, got {len(flag_items)}'
            )
        return FlagsDescription(flag_items, doc)
    elif range_items is not None:
        low, high = get_value_range(range_items, minimum, maximum)
        if name is None:
            return RangeDescription(low, high, formatter, doc)
        else:
            return LabelledRangeDescription(low, high, name, formatter, doc)
    else:
        assert False, 'missing items for description'


def parse_nbo(nbo):
    items = [x.strip() for x in nbo.split(':')]
    if len(items) == 2:
        name, bits = items
        order = None
    elif len(items) == 3:
        name, bits, order = items
        order = int(order, 0)
    else:
        raise ValueError(f'invalid name/bits/order specification')
    return name.strip(), int(bits, 0), order


class FieldBuilder:
    def __init__(self, line_tokens, doc):
        nbo, *flag_tokens = line_tokens
        self.name, self.bits, self.order = parse_nbo(nbo)
        self.flags = parse_flags(
            flag_tokens, 
            {
                'bias': (parse_int, 0),
                'signed': (parse_bool, False),
                'base': (parse_base, hex),
                'fixed': (parse_int, None)
            }
        )
        self.doc = doc
        self.descriptions = []


    def add_description(self, desc):
        self.descriptions.append(desc)


    def create(self, deferred):
        flags = fill_template(self.flags, deferred)
        raw = RawField(
            self.name, self.bits,
            flags['bias'], flags['signed'], flags['fixed'] 
        )
        return self.order, self.bits, flags['fixed'] is not None, Field(
            raw,
            [
                d(raw.minimum, raw.maximum, self.bits, flags['base'])
                for d in self.descriptions
            ],
            self.doc
        )


def make_option(field_builders, deferred):
    # No doc is associated at the Option level.
    fields = []
    fixed_mask = []
    size = 0
    for builder in field_builders:
        order, field_size, is_fixed, field = builder.create(deferred)
        size += field_size
        if order is None:
            fields.append(field)
            fixed_mask.append(is_fixed)
        else:
            fields.insert(order, field)
            fixed_mask.insert(order, is_fixed)
    return size, Option(fields, [i for i, f in enumerate(fixed_mask) if f])


def make_type(option_builders, name, doc, deferred):
    format_option = None
    option_map = {}
    size = None
    for builder in option_builders:
        o_size, option = builder(deferred)
        if size is None:
            size = o_size
        elif size != o_size:
            raise ValueError('options for type must have the same total size')
        if option.arguments in option_map:
            raise ValueError(
                'options for type must have all different argument counts'
            )
        option_map[option.arguments] = option
        if format_option is None:
            format_option = option
    if format_option is None:
        raise ValueError('no options provided for type')
    return Type(name, size, format_option, option_map, doc)


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
                    make_description_maker(line_tokens, doc)
                )
            else: # start a new field.
                current_fields.append(FieldBuilder(line_tokens, doc))
    # Make the last option.
    if not current_fields:
        throw(position, 'option must have at least one field')
    options.append(partial(make_option, current_fields))
    return partial(make_type, options, name, doc)
