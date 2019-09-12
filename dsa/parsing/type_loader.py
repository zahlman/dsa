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
    __accumulator__ = ({}, {})


    def __init__(self):
        # Track where in the accumulator we most recently added a loader.
        self._index = None


    def _categorize(self, section_type):
        return UNKNOWN_SECTION_TYPE.get(
            {
                'flags': (FlagsDescriptionLoader, 0),
                'enum': (EnumDescriptionLoader, 0),
                'type': (MemberLoader, 1)
            }, section_type
        )


    def _parse_section_header(self, tokens):
        section_type, name = INVALID_SECTION_HEADER.pad(tokens, 2, 2)
        return (
            INVALID_SECTION_TYPE.singleton(section_type),
            INVALID_NAME.singleton(name, thing=section_type)
        )


    def indented(self, accumulator, tokens):
        FLOATING_INDENT.require(self._index is not None)
        # Find the most recent loader and delegate to it.
        accumulator[self._index[0]][self._index[1]].add_line(tokens)


    def unindented(self, accumulator, tokens):
        section_type, name = self._parse_section_header(tokens)
        make_loader, index = self._categorize(section_type)
        self._index = index, name
        DUPLICATE_SECTION.add_unique(
            accumulator[index], name, make_loader(), section_type=section_type
        )


def resolve_types(accumulator):
    values, types = accumulator
    lookup = { name: lsm.result() for name, lsm in values.items() }
    return { name: lsm.result(name, lookup) for name, lsm in types.items() }
