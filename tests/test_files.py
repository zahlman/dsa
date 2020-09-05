# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

# System under test.
from dsa.errors import UserError
from dsa.parsing.file_parsing import process, load_lines
# Third-party.
import pytest

good = (
    # Examples from the documentation.
    ('!first @second#third', '+!fourth'),
    ('![1 ,  2  : 3]', '[!4 :  5  , 6] !7 ,  8  : 9'),
    (
        r'''[!example] "double-quoted    \toke\ns [aren't weird]"''',
        r"""![] @[] 'single-quoted:tokens]@!#[aren\'t:weird,either'"""
    ),
    ('    indented', ' !also     ', '+indented', '\t forsooth, indented')
)


expected = (
    (
        (1, '!', [
            ['first'], ['@', 'second'], ['!fourth']
        ]),
    ),
    (
        (1, '!', [
            ['1', '2', '3']
        ]),
        (2, '', [
            ['!4', '5', '6'], ['!7'], ['', ''], ['8'], ['', ''], ['9']
        ])
    ),
    (
        (1, '', [
            ['!example'], ["double-quoted    \toke\ns [aren't weird]"]
        ]),
        (2, '!', [
            [''], ['@', ''], ['single-quoted:tokens]@!#[aren\'t:weird,either']
        ])
    ),
    # Leading whitespace is represented by the first char thereof.
    # (Subsequent code merely checks whether it's '!' or ''.)
    (
        (1, ' ', [['indented']]),
        (2, ' ', [['!also'], ['indented']]),
        (4, '\t', [['forsooth', ''], ['indented']])
    )
)


bad_lines = ('[first][second]', 'first @ second', '[first', '+second]')
bad = (bad_lines[i:] for i in range(len(bad_lines)))


@pytest.mark.parametrize('i,o', zip(good, expected))
def test_process_good(i, o):
    assert tuple(process(i)) == o


@pytest.mark.parametrize('i', bad)
def test_process_bad(i):
    # Each line in the 'bad' sample raises an error, regardless of the
    # subsequent lines.
    with pytest.raises(UserError):
        next(process(i))
