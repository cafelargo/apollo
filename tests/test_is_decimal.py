import pytest

from utils import is_decimal

TEST_CASES = [
    ("", False),
    ("1", True),
    ("0", True),
    ("-1", True),
    ("0.1", True),
    ("-0.1", True),
    ("NaN", True),
    ("NaNanananananan", False),
    (".1", True),
    ("0),1", False),
    ("),1", False),
    ("NULL", False),
    ("None", False),
    ("Infinity", True),
    ("Inf", True),
    ("sNaN", True),
    ("-Inf", True),
    ("-inf", True),
    ("iNF", True),
    ("127.0.0.1", False),
    ("1.2.3", False),
    ("#123456", False),
    ("69%", False),
    ("True", False),
    ("False", False),
    (True, True),
    (False, True),
    ("1_234", True),
    ("!command", False),
    ("2counting2furious", False),
    ("0x123456", False),
    ("0o12345670", False),
    ("1e5", True),
    ("+1e5", True),
    ("1e-5", True),
    ("-1e-5", True),
    ("++1", False),
    ("--1", False),
    ("+-1", False),
    ("-+1", False),
    ("(1)", False),
    ("     1       ", True),
    ("π", False),
]


@pytest.mark.parametrize(["string", "expected"], TEST_CASES)
def test_is_decimal(string, expected):
    actual = is_decimal(string)
    assert actual == expected
