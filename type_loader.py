from description import EnumDescriptionLSM, FlagsDescriptionLSM
from member import OptionLSM, MemberLSM


class TypeDescriptionLSM:
    def __init__(self):
        self.current_section = None
        self.values = {}
        self.options = {}
        self.types = {}


    def _get_dict(self, section_type):
        return {
            'flags': self.values,
            'enum': self.values,
            'option': self.options,
            'type': self.types
        }[section_type]


    def _get_loader(self, section_type):
        return {
            'flags': FlagsDescriptionLSM,
            'enum': EnumDescriptionLSM,
            'option': OptionLSM,
            'type': MemberLSM
        }[section_type]


    def _continue_block(self, line_tokens):
        if self.current_section is None:
            raise ValueError(f'indented line outside block')
        self.current_section.add_line(line_tokens)


    def _next_block(self, line_tokens):
        try:
            section_type, name = line_tokens
        except ValueError:
            raise ValueError(f'invalid section header')
        section = self._get_loader(section_type)()
        container = self._get_dict(section_type)
        if name in container:
            raise ValueError(
                f"duplicate/conflicting definition for '{section_type} {name}'"
            )
        container[name] = section
        self.current_section = section


    def add_line(self, indent, line_tokens):
        (self._continue_block if indent else self._next_block)(line_tokens)


    def result(self):
        description_lookup = {
            name: lsm.result()
            for name, lsm in self.values.items()
        }
        option_lookup = {
            name: lsm.result(description_lookup)
            for name, lsm in self.options.items()
        }
        return {
            name: lsm.result(name, option_lookup)
            for name, lsm in self.types.items()
        }
