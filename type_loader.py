from description import EnumDescriptionLSM, FlagsDescriptionLSM
import errors
from member import OptionLSM, MemberLSM


class UNKNOWN_SECTION_TYPE(errors.MappingError):
    """unrecognized section type `{key}`"""


class FLOATING_INDENT(errors.UserError):
    """indented line outside block"""


class INVALID_SECTION_HEADER(errors.UserError):
    """invalid section header"""


class DUPLICATE_SECTION(errors.MappingError):
    """duplicate or conflicting definition for `{section_type} {key}`"""


class DUPLICATE_TYPE(errors.MappingError):
    """duplicate definition for type `{key}`"""


class TypeDescriptionLSM:
    def __init__(self):
        self._reset()


    def _reset(self):
        self.current_section = None
        self.values = {}
        self.options = {}
        self.types = {}


    def _categorize(self, section_type):
        return UNKNOWN_SECTION_TYPE.get(
            {
                'flags': (FlagsDescriptionLSM, self.values),
                'enum': (EnumDescriptionLSM, self.values),
                'option': (OptionLSM, self.options),
                'type': (MemberLSM, self.types)
            }, section_type
        )


    def _continue_block(self, line_tokens):
        FLOATING_INDENT.require(self.current_section is not None)
        self.current_section.add_line(line_tokens)


    def _next_block(self, line_tokens):
        INVALID_SECTION_HEADER.require(len(line_tokens) == 2)
        section_type, name = line_tokens
        loader, container = self._categorize(section_type)
        section = loader()
        DUPLICATE_SECTION.add_unique(
            container, name, section, section_type=section_type
        )
        self.current_section = section


    def add_line(self, indent, line_tokens):
        (self._continue_block if indent else self._next_block)(line_tokens)


    def end_file(self, label, accumulator):
        # `label` is ignored; we don't care what source the data came from.
        # Add all Member objects to the accumulator.
        description_lookup = {
            name: lsm.result()
            for name, lsm in self.values.items()
        }
        option_lookup = {
            name: lsm.result(description_lookup)
            for name, lsm in self.options.items()
        }
        for name, lsm in self.types.items():
            DUPLICATE_TYPE.add_unique(
                accumulator, name, lsm.result(name, option_lookup)
            )
        self._reset()
