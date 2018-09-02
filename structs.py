from arguments import parameters
import member_template


def instantiate_member(line_tokens):
    tnf, *options = line_tokens
    typename, name, fixed = parts_of(tnf, ':', 1, 3, False)
    member_maker, whitelist = member_template.load(typename)
    params = parameters(whitelist, options)
    if 'before' in params: # hax to change display order of members.
        before = params['before']
        del params['before']
    else:
        before = None
    member = member_maker(params, name)
    return before, member, fixed
