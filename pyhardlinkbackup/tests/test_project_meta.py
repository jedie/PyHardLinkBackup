"""
    Some project meta tests
"""


import pytest
from flake8.main.cli import main as flake8cli


def test_flake8():
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        flake8cli([
            # "--verbose"
        ])

    assert pytest_wrapped_e.value.code == 0
