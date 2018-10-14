from . import errors
from . import line_parsing
from functools import partial
import re


class MISSING_PARAMETER(errors.UserError):
    """missing required parameter for labelled range"""


class FORBIDDEN_PARAMETER(errors.UserError):
    """labelled constant does not take a parameter"""


class PARAMETER_OUT_OF_RANGE(errors.UserError):
    """labelled range parameter is out of range"""


class FORMAT_FAILED(errors.SequenceError):
    """no valid format for value: `{value}`"""


class PARSE_FAILED(errors.SequenceError):
    """couldn't parse: `{text}`"""


class DUPLICATE_FLAG(errors.UserError):
    """duplicate flag names not allowed"""


class INVALID_RANGE(line_parsing.TokenError):
    """invalid range (token should have 1..2 parts, has {actual})"""


class SINGLE_TOKEN_REQUIRED(errors.UserError):
    """{thing} must be a single, single-part token
    (use `[]` to group multiple words; `,` and `:` are not allowed)"""


def _within(low, value, high):
    if low is not None and value < low:
        return False
    if high is not None and value > high:
        return False
    return True


class UnlabelledRange:
    def __init__(self, low, high):
        self.low, self.high = low, high


    def format(self, value, convert):
        return convert(value) if _within(self.low, value, self.high) else None


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
        self.baseline = (
            low if low is not None
            else high if high is not None
            else 0
        )
        self.definite = (low == high == self.baseline)


    def format(self, value, convert):
        return (
            None if not _within(self.low, value, self.high)
            else self.label if self.definite
            else f'{self.label}<{convert(value - self.baseline)}>'
        )


    def _convert_offset(self, param):
        if self.low == self.high:
            FORBIDDEN_PARAMETER.require(param is None)
            return 0
        else:
            MISSING_PARAMETER.require(param is not None)
            return errors.parse_int(param, 'labelled range parameter')


    def parse(self, text):
        match = self.pattern.match(text)
        if match is None:
            return None
        # If the regex matched, the text can't match a different range.
        value = self.baseline + self._convert_offset(match.group(1))
        PARAMETER_OUT_OF_RANGE.require(_within(self.low, value, self.high))
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
        return FORMAT_FAILED.first_not_none(
            (r.format(value, numeric_formatter) for r in self.ranges),
            value=value
        )


    def parse(self, text):
        return PARSE_FAILED.first_not_none(
            (r.parse(text) for r in self.ranges),
            text=text
        )


_flag_splitter = line_parsing.token_splitter('|')


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
        items = _flag_splitter(text)
        set_flags = set(items)
        # FIXME: check for junk flags etc.
        DUPLICATE_FLAG.require(len(items) == len(set_flags))
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


def _parse_range(token):
    low, high = INVALID_RANGE.pad(token, 1, 2)
    if high is None:
        high = low
    return (
        errors.parse_optional_int(low, 'low end of range'),
        errors.parse_optional_int(high, 'high end of range')
    )


def _get_single(token, thing):
    SINGLE_TOKEN_REQUIRED.require(len(token) == 1, thing=thing)
    SINGLE_TOKEN_REQUIRED.require(len(token[0]) == 1, thing=thing)
    return token[0][0]


class EnumDescriptionLSM:
    """Helper used by TypeDescriptionLSM."""
    def __init__(self):
        self.ranges = []


    def add_line(self, line_tokens):
        values, *label = line_tokens
        low, high = _parse_range(values)
        label = _get_single(label, 'enum name') if label else None
        self.ranges.append((low, high, label))


    def result(self):
        return EnumDescription(self.ranges)


class FlagsDescriptionLSM:
    """Helper used by TypeDescriptionLSM."""
    def __init__(self):
        self.names = []


    def add_line(self, line_tokens):
        self.names.append(_get_single(line_tokens, 'flag'))


    def result(self):
        return FlagsDescription(self.names)
