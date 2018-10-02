from parse_config import parts_of
from functools import partial


class EnumDescription:
    def __init__(self, ranges, doc):
        self.ranges = ranges
        self.doc = doc # Unused for now.


    def _format_enum(self, value, numeric_formatter, low, high, label):
        assert low <= value <= high
        if label is None:
            return numeric_formatter(value)
        if low == high:
            return label
        return f'{label}({numeric_formatter(value - low)})'


    def format(self, value, numeric_formatter):
        try:
            match = next(
                (low, high, label)
                for low, high, label in self.ranges
                if low <= value <= high
            )
        except StopIteration:
            raise ValueError(f'No valid format for value: {value}')
        return self._format_enum(value, numeric_formatter, *match)


    def parse(self, text):
        try:
            return next(
                self._parse_enum(text, low, high, label)
                for low, high, label in self.ranges
                if self._ok_enum(text, low, high, label)
            )
        except StopIteration:
            raise ValueError(f"Couldn't parse: {text}")


    def _ok_enum(self, text, low, high, label):
        try:
            # A raw integer must be within range.
            return low <= int(text, 0) <= high
        except ValueError:
            # A labelled value must match the specified label.
            return label is not None and text.startswith(label)


    def _parse_enum(self, text, low, high, label):
        try:
            result = int(text, 0)
            assert low <= result <= high
        except ValueError:
            assert label is not None and text.startswith(label)
            text = text[len(label):]
            if low == high and not text:
                result = low
            elif not (text.startswith('(') and text.endswith(')')):
                raise ValueError('Missing required offset for labelled range')
            else:
                try:
                    result = int(text[1:-1], 0) + low
                except ValueError:
                    raise ValueError('Invalid offset for labelled range')
            if not low <= result <= high:
                raise ValueError('Offset for labelled range out of bounds')
        return result


class FlagsDescription:
    def __init__(self, names, doc):
        self.names = names
        self.doc = doc # Unused for now.


    def format(self, value, numeric_formatter):
        set_flags = []
        for i, name in enumerate(self.names):
            if value & (1 << i):
                set_flags.append(name)
        return ' | '.join(set_flags) if set_flags else numeric_formatter(0)


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


class RawDescription:
    def __init__(self):
        pass


    def format(self, value, numeric_formatter):
        return numeric_formatter(value)


    def parse(self, text):
        return int(text, 0)


Raw = RawDescription()


class EnumDescriptionLSM:
    """Helper used by TypeDescriptionLSM."""
    def __init__(self, doc):
        self.ranges = []
        self.doc = doc


    def add_line(self, line_tokens, doc):
        self.doc.extend(doc)
        values, *label = line_tokens
        low, high = parts_of(values, ':', 1, 2, False)
        if high is None:
            high = low
        if len(label) > 1:
            raise ValueError('Label must be a single token (use [])')
        elif len(label) == 0:
            label = None
        else:
            label = label[0]
        self.ranges.append((int(low, 0), int(high, 0), label))


    def result(self):
        return EnumDescription(self.ranges, self.doc)


class FlagsDescriptionLSM:
    """Helper used by TypeDescriptionLSM."""
    def __init__(self, doc):
        self.names = []
        self.doc = doc


    def add_line(self, line_tokens, doc):
        self.doc.extend(doc)
        assert len(line_tokens) > 0 # empty lines were preprocessed out.
        if len(line_tokens) > 1:
            raise ValueError('Flag must be a single token (use [])')
        self.names.append(line_tokens[0])


    def result(self):
        return FlagsDescription(self.names, self.doc)
