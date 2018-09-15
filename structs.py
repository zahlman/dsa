from arguments import parameters
from parse_config import parts_of
import member_template


def instantiate_member(line_tokens):
    tnf, *options = line_tokens
    typename, name, fixed = parts_of(tnf, ':', 1, 3, False)
    filename = f'{typename}.txt' # For now.
    member_maker, whitelist = member_template.load(filename)
    params = parameters(whitelist, options)
    member = member_maker(params, name)
    return member, fixed
