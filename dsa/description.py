from .errors import SequenceError, UserError
from .parsing.line_parsing import line_parser, token_splitter
from .parsing.token_parsing import make_parser, single_parser
from functools import partial
import re


class INVALID_INTERVAL_RANGE(UserError):
    """bottom of range may not exceed top of range"""


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


class FLAGS_NOT_ALLOWED(UserError):
    """an enum is required (not flags) for {purpose}"""


class DUPLICATE_FLAG(UserError):
    """duplicate flag names not allowed"""


class BAD_DESCRIPTION_HEADER(UserError):
    """extra data not allowed in `enum` or `flags` header"""


class _Interval:
    def __init__(self, bottom, top, stride):
        if stride is None:
            stride = 1
        INVALID_INTERVAL_RANGE.require(
            bottom is None or top is None or bottom <= top
        )
        self._baseline = (
            bottom if bottom is not None
            else top if top is not None
            else 0
        )
        self._low_index = (
            None if bottom is None
            else (bottom - self._baseline) // stride
        )
        self._high_index = (
            None if top is None
            else (top - self._baseline) // stride
        )
        self._stride = stride


    @property
    def definite(self):
        return self._low_index == self._high_index != None


    def index(self, value):
        raw, remainder = divmod(value - self._baseline, self._stride)
        if remainder:
            return None
        if self._low_index is not None and raw < self._low_index:
            return None
        if self._high_index is not None and raw > self._high_index:
            return None
        return raw


    def __getitem__(self, index):
        result = self._baseline + (index * self._stride)
        PARAMETER_OUT_OF_RANGE.require(result in self)
        return result


    def __contains__(self, value):
        return self.index(value) is not None


class UnlabelledRange:
    def __init__(self, interval):
        self._interval = interval


    def pointer_value(self, value):
        return value if value in self._interval else None


    def label(self, value):
        return None


    def format(self, value, convert):
        return convert(value) if value in self._interval else None


    def parse(self, text):
        try:
            value = int(text, 0)
        except ValueError:
            return None # might be matched by a LabelledRange!
        else:
            return value if value in self._interval else None


_labelled_range_parameter = single_parser('labelled range parameter', 'integer')


class LabelledRange:
    def __init__(self, interval, label):
        self._interval = interval
        self._label = label
        self._pattern = re.compile(
            f'(?:{re.escape(label)})(?:<(.*)>)?$'
        )


    def pointer_value(self, value):
        # A pointer is valid only if the enum would not label it.
        return None


    def label(self, value):
        index = self._interval.index(value)
        return (
            None if index is None
            else self._label if self._interval.definite
            else None
        )


    def format(self, value, convert):
        index = self._interval.index(value)
        return (
            None if index is None
            else self._label if self._interval.definite
            else f'{self._label}<{convert(index)}>'
        )


    def _convert_offset(self, param):
        if self._interval.definite:
            FORBIDDEN_PARAMETER.require(param is None)
            return 0
        else:
            MISSING_PARAMETER.require(param is not None)
            return _labelled_range_parameter([param])


    def parse(self, text):
        match = self._pattern.match(text)
        if match is None:
            return None
        # If the regex matched, the text can't match a different range.
        index = self._convert_offset(match.group(1))
        return self._interval[index]


class EnumDescription:
    def __init__(self, ranges):
        self._ranges = ranges


    def pointer_value(self, value):
        for r in self._ranges:
            result = r.pointer_value(value)
            if result is not None:
                return result
        return None # not an error, just no pointer to chase here.


    def label(self, value):
        for r in self._ranges:
            result = r.label(value)
            if result is not None:
                return result
        return None # not an error, just no label for this line.


    def format(self, value, numeric_formatter):
        return FORMAT_FAILED.first_not_none(
            (r.format(value, numeric_formatter) for r in self._ranges),
            value=value
        )


    def parse(self, text):
        return PARSE_FAILED.first_not_none(
            (r.parse(text) for r in self._ranges),
            text=text
        )


_flag_splitter = token_splitter('|')


class FlagsDescription:
    def __init__(self, names):
        self._names = names


    def pointer_value(self, value):
        raise FLAGS_NOT_ALLOWED(purpose='determining pointer validity')


    def label(self, value):
        raise FLAGS_NOT_ALLOWED(purpose='labelling structs in a group')


    def format(self, value, numeric_formatter):
        set_flags = []
        for i, name in enumerate(self._names):
            if value & (1 << i):
                set_flags.append(name)
        return ' | '.join(set_flags) if set_flags else numeric_formatter(0)


    def parse(self, text):
        value = 0
        # Special case for no flags set.
        try:
            zero = int(text, 0)
        except ValueError:
            pass
        else:
            if zero == 0:
                return 0
        items = _flag_splitter(text)
        set_flags = set(items)
        DUPLICATE_FLAG.require(len(items) == len(set_flags))
        for i, name in enumerate(self._names):
            if name in set_flags:
                value |= 1 << i
                set_flags.remove(name)
        # FIXME: Is it really not an error if there are leftover set_flags?
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
        return _Interval(low, low, 1)
    else:
        return _Interval(*_enum_range_parser(token))


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
        self._ranges = []


    def add_line(self, line_tokens):
        interval, label = _enum_description_parser(line_tokens)
        # FIXME: take `stride` into consideration
        self._ranges.append(
            UnlabelledRange(interval) if label is None
            else LabelledRange(interval, label)
        )


    def result(self):
        return EnumDescription(self._ranges)


_flag_name = line_parser(
    'description of flag option',
    single_parser('name', 'string'),
    required=1
)


class FlagsDescriptionLoader:
    """Helper used by TypeDescriptionLoader."""
    def __init__(self, tokens):
        BAD_DESCRIPTION_HEADER.require(not tokens)
        self._names = []


    def add_line(self, line_tokens):
        self._names.append(_flag_name(line_tokens)[0])


    def result(self):
        return FlagsDescription(self._names)
