# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

# System under test.
from dsa.ui.dsd import dsd, root_data
from dsa.errors import UserError
# Third-party.
import pytest


def _important_lines(filename):
    with open(filename) as f:
        return [
            line for line in (line.rstrip() for line in f)
            if line != '' and not line.startswith('#')
        ]


def _validate(reference, base_name):
    # The generated file exactly matches a reference expectation file.
    actual = _important_lines(f'{base_name}.txt')
    expected = _important_lines(reference / f'{base_name}.txt')
    assert actual == expected


def test_input(environment):
    with open('test.bin', 'rb') as f:
        data = f.read()
    assert list(data) == list(range(256))


def _dsd_wrapper(root_text, output, *paths):
    dsd('test.bin', root_data(root_text), output, target='dsd', paths=paths)


def test_disassemble_hexdump(environment):
    _dsd_wrapper('0:hex', 'test_hex.txt')
    _validate(environment[1], 'test_hex')


def test_disassemble_partial(environment):
    _dsd_wrapper('0x81:hex', 'test_hex_partial.txt')
    _validate(environment[1], 'test_hex_partial')


def test_use_local(capsys, environment):
    # It uses the local config when and only when requested.
    # Values are little-endian.
    _dsd_wrapper('0:example', 'test_example.txt', 'lib')
    _validate(environment[1], 'test_example')
    # When the local config isn't available, it disassembles empty blocks
    # and displays a warning.
    _dsd_wrapper('0:example', 'test_example2.txt')
    outtxt = capsys.readouterr().out
    assert 'Warning: will skip chunk of unknown type example' in outtxt
    _validate(environment[1], 'test_example2')


def test_consider_align(environment):
    # It respects the 'align' specified in the structgroup.
    with pytest.raises(UserError):
        _dsd_wrapper('3:example', 'test_example3.txt', 'lib')


def test_signedness(environment):
    # It properly considers the signedness of types.
    _dsd_wrapper('4:example', 'test_example3.txt', 'lib')
    _validate(environment[1], 'test_example3')
