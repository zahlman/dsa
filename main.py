from parse_config import cached_loader
from type_loader import TypeDescriptionLSM
from structgroup_loader import StructGroupDescriptionLSM
from functools import partial
from itertools import count


def make_structgroup_loader(
    type_paths=('types',), struct_paths=('structgroups',)
):
    load_type = cached_loader(TypeDescriptionLSM, type_paths)
    return cached_loader(
        partial(StructGroupDescriptionLSM, load_type), struct_paths
    )


def format_chunk(group, group_name, label, source, position):
    total = 0
    previous = None
    lines = [f'@label {label} 0x{position:X}', None, f'@group {group_name} {{']
    for i in count():
        result = group.format_from(source, position, previous, i)
        if result is None:
            break
        previous, (tokens, size) = result
        lines.append(f"{previous} {' '.join(tokens)}")
        position += size
        total += size
    lines[1] = f'@filter size {total} {{'
    lines.extend(['}', '}'])
    return lines


def disassemble(load_structgroup, group_name, source, position, outfile):
    structgroup = load_structgroup(group_name)
    with open(outfile, 'w') as f:
        for line in format_chunk(
            structgroup, group_name, 'main', source, position
        ):
            f.write(line + '\n')


def test(group_name, infile, outfile, type_paths, struct_paths, position):
    with open(infile, 'rb') as f:
        data = f.read()
    disassemble(
        make_structgroup_loader(type_paths, struct_paths),
        group_name, data, position, outfile
    )
