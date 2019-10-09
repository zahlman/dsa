from .errors import SequenceError, UserError
from .parsing.line_parsing import line_parser, token_splitter
from .parsing.token_parsing import make_parser, single_parser
from functools import partial
import re


class MISSING_PARAMETER(UserError):
    """missing required parameter for labelled range"""


class FORBIDDEN_PARAMETER(UserError):
    """labelled constant does not take a parameter"""


class PARAMETER_OUT_OF_RANGE(UserError):
    """labelled range parameter is out of range"""


class FORMAT_FAILED(SequenceError):
    """no valid format for value: `{value}`"""


class PARSE_FAILED(SequenceError):
    """couldn't parse: `{text}`"""


class DUPLICATE_FLAG(UserError):
    """duplicate flag names not allowed"""


class BAD_DESCRIPTION_HEADER(UserError):
    """extra data not allowed in `enum` or `flags` header"""


def _within(low, value, high):
    if low is not None and value < low:
        return False
    if high is not None and value > high:
        return False
    return True


class UnlabelledRange:
    def __init__(self, low, high):
        self.low, self.high = low, high


    def pointer_value(self, value):
        return value if _within(self.low, value, self.high) else None


    def format(self, value, convert):
        return convert(value) if _within(self.low, value, self.high) else None


    def parse(self, text):
        try:
            value = int(text, 0)
            return value if self.low <= value <= self.high else None
        except ValueError:
            return None # might be matched by a LabelledRange!


_labelled_range_parameter = single_parser('labelled range parameter', 'integer')


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


    @property
    def definite(self):
        return self.low == self.high and self.low is not None


    def pointer_value(self, value):
        # A pointer is valid only if the enum would not label it.
        return None


    def format(self, value, convert):
        return (
            None if not _within(self.low, value, self.high)
            else self.label if self.definite
            else f'{self.label}<{convert(value - self.baseline)}>'
        )


    def _convert_offset(self, param):
        if self.definite:
            FORBIDDEN_PARAMETER.require(param is None)
            return 0
        else:
            MISSING_PARAMETER.require(param is not None)
            return _labelled_range_parameter([param])


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


    def pointer_value(self, value):
        for r in self.ranges:
            result = r.pointer_value(value)
            if result is not None:
                return result
        return None # not an error, just no pointer to chase here.


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


_flag_splitter = token_splitter('|')


class FlagsDescription:
    def __init__(self, names):
        self.names = names


    def pointer_value(self, value):
        raise Exception # FIXME
        # a Pointer should only be allowed to have an EnumDescription.


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


_field_value = single_parser('field value', 'integer')


class RawDescription:
    def __init__(self):
        pass


    def pointer_value(self, value):
        return value


    def format(self, value, numeric_formatter):
        return numeric_formatter(value)


    def parse(self, text):
        return _field_value([text])


Raw = RawDescription()


_enum_value_parser = single_parser('value', 'integer')


_enum_range_parser = make_parser(
    'range',
    ('integer?', 'low value'),
    ('integer?', 'high value'),
    ('integer?', 'stride')
)


def _parse_range(token):
    # We need to distinguish a single-part token from one that has
    # empty parts; but a 2-part token works the same as a 3-part one with
    # an empty third part.
    if len(token) == 1:
        low = _enum_value_parser(token)
        return (low, low, 1)
    else:
        return _enum_range_parser(token)


_enum_description_parser = line_parser(
    'description of enumeration option',
    _parse_range,
    # when the name is absent, an UnlabelledRange is produced.
    single_parser('name', 'string?'),
    required=1
)


class EnumDescriptionLoader:
    """Helper used by TypeDescriptionLoader."""
    def __init__(self, tokens):
        BAD_DESCRIPTION_HEADER.require(not tokens)
        self.ranges = []


    def add_line(self, line_tokens):
        (low, high, stride), label = _enum_description_parser(line_tokens)
        # FIXME: take `stride` into consideration
        self.ranges.append((low, high, label))


    def result(self):
        return EnumDescription(self.ranges)


_flag_name = line_parser(
    'description of flag option',
    single_parser('name', 'string'),
    required=1
)


class FlagsDescriptionLoader:
    """Helper used by TypeDescriptionLoader."""
    def __init__(self, tokens):
        BAD_DESCRIPTION_HEADER.require(not tokens)
        self.names = []


    def add_line(self, line_tokens):
        self.names.append(_flag_name(line_tokens)[0])


    def result(self):
        return FlagsDescription(self.names)
