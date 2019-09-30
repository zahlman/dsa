from ..description import EnumDescriptionLoader, FlagsDescriptionLoader
from ..errors import MappingError, UserError
from ..member import ValueLoader, PointerLoader
from .file_parsing import SimpleLoader
from .line_parsing import TokenError
from .token_parsing import make_parser


class FLOATING_INDENT(UserError):
    """indented line outside block"""


class INVALID_SECTION_HEADER(TokenError):
    """invalid section header (must have 2 tokens; has {actual} tokens)"""


class DUPLICATE_SECTION(MappingError):
    """duplicate or conflicting definition for `{section_type} {key}`"""


class TypeLoader(SimpleLoader):
    def __init__(self):
        # Either a DescriptionLoader from self._descriptions
        # or a MemberLoader from self._members.
        self._current_datum = None
        self._descriptions = {}
        self._members = {}
        self._section_parser = make_parser(
            'section type',
            ({
                'flags': (FlagsDescriptionLoader, self._descriptions),
                'enum': (EnumDescriptionLoader, self._descriptions),
                'type': (ValueLoader, self._members),
                'pointer': (PointerLoader, self._members)
            }, 'section type')
        )


    def _parse_section_header(self, tokens):
        INVALID_SECTION_HEADER.require(len(tokens) >= 2)
        section_type, name, *flags = tokens
        return (
            self._section_parser(section_type)[0],
            make_parser(section_type, ('string', section_type))(name)[0],
            flags
        )


    def indented(self, tokens):
        FLOATING_INDENT.require(self._current_datum is not None)
        self._current_datum.add_line(tokens)


    def unindented(self, tokens):
        section_type, name, flags = self._parse_section_header(tokens)
        cls, storage = section_type
        self._current_datum = cls(flags)
        DUPLICATE_SECTION.add_unique(
            storage, name, self._current_datum, section_type=section_type
        )


    def result(self):
        lookup = {
            name: lsm.result() for name, lsm in self._descriptions.items()
        }
        return {
            name: lsm.result(name, lookup)
            for name, lsm in self._members.items()
        }
