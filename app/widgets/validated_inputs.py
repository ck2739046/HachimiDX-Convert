from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtGui import QDoubleValidator, QIntValidator
from PyQt6.QtWidgets import QLineEdit

from app import ui_style


@dataclass(frozen=True, slots=True)
class ValidationResult:
    value: int | float | None
    error: str | None


class ValidatedLineEdit(QLineEdit):
    """A validated input modeled after legacy ValidatedLineEdit.

    - value_type: 'int' or 'double'
    - decimals: only used for 'double'

    Call get_value() to retrieve parsed value + error message.
    """

    def __init__(
        self,
        *,
        value_type: str,
        min_val: int | float,
        max_val: int | float,
        decimals: int = 3,
        width: int | None = None,
        placeholder: str | None = None,
        parent=None,
    ):
        super().__init__(parent)

        if value_type not in ("int", "double"):
            raise ValueError("value_type must be 'int' or 'double'")

        if min_val >= max_val:
            raise ValueError("min_val must be < max_val")

        self.value_type = value_type
        self.min_val = min_val
        self.max_val = max_val
        self.decimals = 0 if value_type == "int" else int(decimals)

        self.setStyleSheet(f"background-color: {ui_style.COLORS['grey']}; padding-left: 8px;")

        if width is not None:
            self.setFixedSize(width, ui_style.element_height)
        else:
            self.setFixedHeight(ui_style.element_height)

        if placeholder:
            self.setPlaceholderText(placeholder)

        if value_type == "int":
            self.setValidator(QIntValidator(int(min_val), int(max_val), self))
        else:
            dv = QDoubleValidator(float(min_val), float(max_val), self.decimals, self)
            dv.setNotation(QDoubleValidator.Notation.StandardNotation)
            self.setValidator(dv)

    def get_value(self) -> ValidationResult:
        text = self.text().strip()
        if not text:
            return ValidationResult(None, f"Invalid value: input is empty. Expected {self.value_type} in range [{self.min_val}, {self.max_val}].")

        try:
            if self.value_type == "int":
                value = int(text)
            else:
                value = round(float(text), self.decimals)

            if value < self.min_val or value > self.max_val:
                return ValidationResult(None, f"Invalid value: out of range. Expected {self.value_type} in range [{self.min_val}, {self.max_val}].")

            return ValidationResult(value, None)
        except ValueError:
            return ValidationResult(None, f"Invalid value: format error. Expected {self.value_type} in range [{self.min_val}, {self.max_val}].")


class OptionalFloatLineEdit(ValidatedLineEdit):
    """A validated float input that allows empty value."""

    def get_value(self) -> ValidationResult:
        text = self.text().strip()
        if not text:
            return ValidationResult(None, None)
        return super().get_value()


class OptionalSignedFloatLineEdit(QLineEdit):
    """Optional float input that allows negative values.

    Use this for fields like trim_end_sec where negative values are meaningful.
    """

    def __init__(
        self,
        *,
        min_val: float,
        max_val: float,
        decimals: int = 3,
        width: int | None = None,
        placeholder: str | None = None,
        parent=None,
    ):
        super().__init__(parent)

        if min_val >= max_val:
            raise ValueError("min_val must be < max_val")

        self.min_val = float(min_val)
        self.max_val = float(max_val)
        self.decimals = int(decimals)

        self.setStyleSheet(f"background-color: {ui_style.COLORS['grey']}; padding-left: 8px;")

        if width is not None:
            self.setFixedSize(width, ui_style.element_height)
        else:
            self.setFixedHeight(ui_style.element_height)

        if placeholder:
            self.setPlaceholderText(placeholder)

        dv = QDoubleValidator(self.min_val, self.max_val, self.decimals, self)
        dv.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.setValidator(dv)

    def get_value(self) -> ValidationResult:
        text = self.text().strip()
        if not text:
            return ValidationResult(None, None)

        try:
            value = round(float(text), self.decimals)
            if value < self.min_val or value > self.max_val:
                return ValidationResult(
                    None,
                    f"Invalid value: out of range. Expected double in range [{self.min_val}, {self.max_val}].",
                )
            return ValidationResult(value, None)
        except ValueError:
            return ValidationResult(
                None,
                f"Invalid value: format error. Expected double in range [{self.min_val}, {self.max_val}].",
            )
