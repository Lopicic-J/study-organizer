import pytest
from study_organizer.service.validation import validate_iso_date, validate_module_code
from study_organizer.service.errors import ValidationError


def test_validate_module_code_upper():
    assert validate_module_code("se101") == "SE101"


def test_validate_module_code_rejects_bad():
    with pytest.raises(ValidationError):
        validate_module_code("S-101")


def test_validate_iso_date_ok():
    assert validate_iso_date("2026-03-05") == "2026-03-05"


def test_validate_iso_date_bad():
    with pytest.raises(ValidationError):
        validate_iso_date("2026-99-99")
