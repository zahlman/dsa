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


_section_header_parser = line_parser(
    'section header',
    single_parser(
        'type',
        {'flags', 'enum', 'type', 'pointer'}
    ),
    single_parser('name', 'string'),
    required=2, more=True
)


class TypeLoader(SimpleLoader):
    def __init__(self):
        # Either a DescriptionLoader from self._descriptions
        # or a MemberLoader from self._members.
        self._current_datum = None
        self._descriptions = {}
        self._members = {}


    def _dispatch(self, name):
        return {
            'flags': (FlagsDescriptionLoader, self._descriptions),
            'enum': (EnumDescriptionLoader, self._descriptions),
            'type': (ValueLoader, self._members),
            'pointer': (PointerLoader, self._members)
        }[name]


    def indented(self, tokens):
        FLOATING_INDENT.require(self._current_datum is not None)
        self._current_datum.add_line(tokens)


    def unindented(self, tokens):
        typename, name, flags = _section_header_parser(tokens)
        loader, storage = self._dispatch(typename)
        # Set up a new loader and also remember it in the appropriate category.
        self._current_datum = loader(flags)
        DUPLICATE_SECTION.add_unique(
            storage, name, self._current_datum, section_type=typename
        )


    def result(self):
        description_lookup = {
            name: lsm.result() for name, lsm in self._descriptions.items()
        }
        return description_lookup, {
            name: lsm.result(name, description_lookup)
            for name, lsm in self._members.items()
        }
