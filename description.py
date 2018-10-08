from parse_config import parts_of
from functools import partial
import re


class UnlabelledRange:
    def __init__(self, low, high):
        self.low, self.high = low, high


    def format(self, value, convert):
        return convert(value) if self.low <= value <= self.high else None


    def parse(self, text):
        try:
            value = int(text, 0)
            return value if self.low <= value <= self.high else None
        except ValueError:
            return None # might be matched by a LabelledRange!


class LabelledRange:
    def __init__(self, low, high, label):
        self.low, self.high = low, high
        self.label = label
        self.pattern = re.compile(
            f'(?:{re.escape(label)})(?:<(.*)>)?$'
        )


    def format(self, value, convert):
        low, high, label = self.low, self.high, self.label
        if not low <= value <= high:
            return None
        return label if low == high else f'{label}<{convert(value - low)}>'


    def _convert_offset(self, param):
        need_param = self.low != self.high
        if param is None:
            if need_param:
                raise ValueError(
                    'missing required parameter for labelled range'
                )
            return 0
        if not need_param:
            raise ValueError('labelled constant does not take a parameter')
        try:
            return int(param, 0)
        except ValueError:
            raise ValueError('labelled range parameter must be integer')


    def parse(self, text):
        match = self.pattern.match(text)
        if match is None:
            return None
        value = self.low + self._convert_offset(match.group(1))
        if not self.low <= value <= self.high:
            # This can't match another range.
            raise ValueError('labelled range parameter is out of range')
        return value


class EnumDescription:
    def __init__(self, ranges):
        self.ranges = [
            UnlabelledRange(low, high)
            if label is None
            else LabelledRange(low, high, label)
            for low, high, label in ranges
        ]


    def format(self, value, numeric_formatter):
        candidates = (
            r.format(value, numeric_formatter)
            for r in self.ranges
        )
        try:
            return next(c for c in candidates if c is not None)
        except StopIteration:
            raise ValueError(f'No valid format for value: {value}')


    def parse(self, text):
        candidates = (
            r.parse(text)
            for r in self.ranges
        )
        try:
            return next(c for c in candidates if c is not None)
        except StopIteration:
            raise ValueError(f"Couldn't parse: {text}")


class FlagsDescription:
    def __init__(self, names):
        self.names = names


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
    def __init__(self):
        self.ranges = []


    def add_line(self, line_tokens):
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
        return EnumDescription(self.ranges)


class FlagsDescriptionLSM:
    """Helper used by TypeDescriptionLSM."""
    def __init__(self):
        self.names = []


    def add_line(self, line_tokens):
        assert len(line_tokens) > 0 # empty lines were preprocessed out.
        if len(line_tokens) > 1:
            raise ValueError('Flag must be a single token (use [])')
        self.names.append(line_tokens[0])


    def result(self):
        return FlagsDescription(self.names)
