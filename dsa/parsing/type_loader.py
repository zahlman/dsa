from ..description import EnumDescriptionLoader, FlagsDescriptionLoader
from ..errors import MappingError, UserError
from ..member import MemberLoader
from .file_parsing import SimpleLoader
from .line_parsing import TokenError


class UNKNOWN_SECTION_TYPE(MappingError):
    """unrecognized section type `{key}`"""


class FLOATING_INDENT(UserError):
    """indented line outside block"""


class INVALID_SECTION_HEADER(TokenError):
    """invalid section header (must have 2 tokens; has {actual} tokens)"""


class INVALID_SECTION_TYPE(TokenError):
    """invalid section type (token must be single-part; has {actual} parts)"""


class INVALID_NAME(TokenError):
    """invalid {thing} name (token must be single-part; has {actual} parts)"""


class DUPLICATE_SECTION(MappingError):
    """duplicate or conflicting definition for `{section_type} {key}`"""


class DUPLICATE_TYPE(MappingError):
    """duplicate definition for type `{key}`"""


class TypeLoader(SimpleLoader):
    def __init__(self):
        # Either a DescriptionLoader from self._descriptions
        # or a MemberLoader from self._members.
        self._current_datum = None
        self._descriptions = {}
        self._members = {}


    def _categorize(self, section_type):
        return UNKNOWN_SECTION_TYPE.get(
            {
                'flags': (FlagsDescriptionLoader, self._descriptions),
                'enum': (EnumDescriptionLoader, self._descriptions),
                'type': (MemberLoader, self._members)
            }, section_type
        )


    def _parse_section_header(self, tokens):
        section_type, name = INVALID_SECTION_HEADER.pad(tokens, 2, 2)
        return (
            INVALID_SECTION_TYPE.singleton(section_type),
            INVALID_NAME.singleton(name, thing=section_type)
        )


    def indented(self, tokens):
        FLOATING_INDENT.require(self._current_datum is not None)
        self._current_datum.add_line(tokens)


    def unindented(self, tokens):
        section_type, name = self._parse_section_header(tokens)
        cls, storage = self._categorize(section_type)
        self._current_datum = cls()
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
