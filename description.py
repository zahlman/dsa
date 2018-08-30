from functools import partial


class LabelledRangeDescription:
    def __init__(self, lowest, highest, label, numeric_formatter, doc):
        self.lowest = lowest
        self.highest = highest
        self.label = label
        self.numeric_formatter = numeric_formatter
        # When parsing, any base is allowed with the appropriate prefix.
        self.doc = doc # Unused for now.


    def __str__(self):
        label = self.label
        low = self.numeric_formatter(self.lowest)
        high = self.numeric_formatter(self.highest)
        size = self.highest - self.lowest
        name = 'LabelledRangeDescription'
        if size:
            return f'{name}: {label}(0)={low} .. {label}({size})={high}'
        return f'{name}: {label}={low}'


    def format(self, value):
        if value < self.lowest or value > self.highest:
            # Might still be representable another way.
            return None
        text = self.numeric_formatter(value)
        # Special case: when the range describes a single number, the label
        # is not annotated with an offset.
        if self.lowest == self.highest:
            return self.label
        # Otherwise, it's annotated thus:
        offset = value - self.lowest
        return f'{self.label}({text})'


    def parse(self, text):
        if not text.startswith(self.label):
            # Might still correspond to a different Description.
            return None
        text = text[len(self.label):]
        # Is this the short form with an annotation not required?
        if (self.lowest == self.highest) and not text:
            return self.lowest
        # If the annotation isn't present, flag an error.
        # This means that if one label for a Field value is a substring of
        # another, the longer one needs to be checked first.
        if not (text.startswith('(') and text.endswith(')')):
            raise ValueError('Missing offset for labelled range')
        value = int(text[1:-1], 0) + self.lowest
        if value < self.lowest or value > self.highest:
            raise ValueError('Invalid offset for labelled range')
        return value


class RangeDescription:
    def __init__(self, lowest, highest, numeric_formatter, doc):
        self.lowest = lowest
        self.highest = highest
        self.numeric_formatter = numeric_formatter
        # When parsing, any base is allowed with the appropriate prefix.
        self.doc = doc # Unused for now.


    def __str__(self):
        low = self.numeric_formatter(self.lowest)
        high = self.numeric_formatter(self.highest)
        if self.lowest == self.highest:
            return f'RangeDescription: {low}'
        else:
            return f'RangeDescription: {low} .. {high}'


    def format(self, value):
        if value < self.lowest or value > self.highest:
            # Might still be representable another way.
            return None
        return self.numeric_formatter(value)


    def parse(self, text):
        try:
            value = int(text, 0)
        except ValueError:
            # Might still correspond to a different Description.
            return None
        # If the value is out of range, it might *still* correspond
        # to a different Description (for another range).
        return value if self.lowest <= value <= self.highest else None


class FlagsDescription:
    def __init__(self, names, doc):
        self.names = names
        self.doc = doc # Unused for now.


    def __str__(self):
        return f"FlagsDescription: {' | '.join(self.names)}"


    def format(self, value):
        set_flags = []
        for i, name in enumerate(self.names):
            if value & (1 << i):
                set_flags.append(name)
        return ' | '.join(set_flags)


    def parse(self, text):
        value = 0
        items = [t.strip() for t in text.split('|')]
        set_flags = set(items)
        if len(items) != len(set_flags):
            raise ValueError('Duplicate flag names not allowed')
        for i, name in enumerate(self.names):
            if name in set_flags:
                value |= 1 << i
                set_flags.remove(name)
        # If there were names left over, this data might still
        # correspond to a different Description. This happens
        # in particular when there was only a single name.
        return None if set_flags else value


def _is_number_or_blank(text):
    if not text:
        return True
    try:
        int(text, 0)
        return True
    except ValueError:
        return False


def _normalize_range(items, minimum, maximum):
    count = len(items)
    if count > 2:
        raise ValueError('too many parameters for range description')
    
    if count == 2:
        low, high = items
        low = int(low, 0) if low else minimum
        high = int(high, 0) if high else maximum
        if low < minimum or high > maximum:
            raise ValueError(
                f"range {low}..{high} can't be represented by this field"
            )
        return low, high
    
    # can't be empty here; if there was a label, it would have been
    # parsed as a flag name, and otherwise the line would be empty.
    assert count == 1
    value = items[0]
    if not value:
        # This only happens for a LabelledRangeDescription (e.g. `foo:`);
        # otherwise, the whole line would be empty.
        raise ValueError('no range given for labelled range description')
    value = int(value, 0)
    if not minimum <= value <= maximum:
        raise ValueError(
            f"value {value} can't be represented by this field"
        )
    return value, value


def _rd(
    range_items, doc, minimum, maximum, bits, formatter
):
    low, high = _normalize_range(range_items, minimum, maximum)
    return RangeDescription(low, high, formatter, doc)


def _lrd(
    name, range_items, doc, minimum, maximum, bits, formatter
):
    low, high = _normalize_range(range_items, minimum, maximum)
    return LabelledRangeDescription(low, high, name, formatter, doc)


def _fd(
    flag_items, doc, minimum, maximum, bits, formatter
):
    if len(flag_items) != bits:
        raise ValueError(
            f'expected {bits} flags, got {len(flag_items)}'
        )
    return FlagsDescription(flag_items, doc)


def description_maker(line_tokens, doc):
    """Creates a factory that will create a Description using deferred info.
    line_tokens -> tokenized line from the config file.
    doc -> associated doc lines.
    The factory expects the following parameters:
    minimum -> lowest describable value.
    maximum -> highest describable value.
    bits -> number of bits used to represent the value.
    formatter -> preferred formatting function for int->str conversion."""
    if len(line_tokens) != 1:
        raise ValueError('field description must be a single token')
    items = [t.strip() for t in line_tokens[0].split(':')]
    if not any(_is_number_or_blank(i) for i in items):
        return partial(_fd, items, doc)
    elif _is_number_or_blank(items[0]):
        return partial(_rd, items, doc)
    else:
        name, *items = items
        return partial(_lrd, name, items, doc)
