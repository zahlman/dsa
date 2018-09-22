from parse_config import cached_loader
from type_loader import TypeDescriptionLSM
from structgroup_loader import StructGroupDescriptionLSM
from functools import partial


def make_structgroup_loader():
    load_type = cached_loader(TypeDescriptionLSM, ['types'])
    return cached_loader(
        partial(StructGroupDescriptionLSM, load_type), ['structgroups']
    )


def disassemble(load_structgroup, group_name, source, position, outfile):
    structgroup = load_structgroup(group_name)
    with open(outfile, 'w') as f:
        f.write(f'@group {group_name} {{')
        for line in structgroup.format_chunk(source, position):
            f.write(line)
        f.write('}')


def test(group_name, infile, outfile):
    with open(infile, 'rb') as f:
        data = f.read()
    disassemble(make_structgroup_loader(), group_name, data, 0, outfile)
