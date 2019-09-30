from ..description import EnumDescriptionLoader, FlagsDescriptionLoader
from ..errors import MappingError, UserError
from ..member import ValueLoader, PointerLoader
from .file_parsing import SimpleLoader
from .line_parsing import line_parser
from .token_parsing import single_parser


class FLOATING_INDENT(UserError):
    """indented line outside block"""


class DUPLICATE_SECTION(MappingError):
    """duplicate or conflicting definition for `{section_type} {key}`"""


class TypeLoader(SimpleLoader):
    def __init__(self):
        # Either a DescriptionLoader from self._descriptions
        # or a MemberLoader from self._members.
        self._current_datum = None
        self._descriptions = {}
        self._members = {}
        self._section_header_parser = line_parser(
            'section header',
            single_parser(
                'type',
                {
                    # When this value is parsed, "convert" it such that we
                    # obtain the corresponding loader and storage location,
                    # but also remember the original text for error reporting.
                    'flags': ('flags', FlagsDescriptionLoader, self._descriptions),
                    'enum': ('enum', EnumDescriptionLoader, self._descriptions),
                    'type': ('type', ValueLoader, self._members),
                    'pointer': ('pointer', PointerLoader, self._members)
                }
            ),
            single_parser('name', 'string'),
            required=2, more=True
        )


    def indented(self, tokens):
        FLOATING_INDENT.require(self._current_datum is not None)
        self._current_datum.add_line(tokens)


    def unindented(self, tokens):
        section, name, flags = self._section_header_parser(tokens)
        typename, loader, storage = section
        # Set up a new loader and also remember it in the appropriate category.
        self._current_datum = loader(flags)
        DUPLICATE_SECTION.add_unique(
            storage, name, self._current_datum, section_type=typename
        )


    def result(self):
        lookup = {
            name: lsm.result() for name, lsm in self._descriptions.items()
        }
        return {
            name: lsm.result(name, lookup)
            for name, lsm in self._members.items()
        }
