"""Badge configuration data models with JSON serialization."""

from dataclasses import dataclass, field, asdict
from typing import List, Optional
import json


@dataclass
class ConditionalRule:
    """Conditional output for a field.

    Two match modes:
      - "y" (default): cell must start with 'Y'. Output = text + trailing-after-Y.
      - "non_dash": cell must be non-blank and not just '-'. Output = text + cell.
    """
    column: str = ""
    text: str = ""
    match: str = "y"  # "y" or "non_dash"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ConditionalRule":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class FieldPlacement:
    """One text field positioned on the badge."""
    csv_column: str = ""
    x: float = 0.0
    y: float = 0.0
    font_family: str = "Arial"
    font_size: int = 24
    font_color: str = "#000000"
    bold: bool = False
    italic: bool = False
    alignment: str = "center"  # "left", "center", "right"
    max_width: int = 0  # 0 = no limit; otherwise auto-shrink text or wrap
    wrap: bool = False  # if True with max_width > 0, word-wrap instead of shrinking
    line_height: float = 1.0  # multiplier of natural line height for wrapped text
    side: str = "front"  # "front" or "back"
    # When non-empty, the field renders this literal text and ignores csv_column/rules.
    static_text: str = ""
    # When non-empty, the field's text is resolved from these rules instead of csv_column.
    rules: List[ConditionalRule] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["rules"] = [r.to_dict() for r in self.rules]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "FieldPlacement":
        d = dict(d)
        rules_data = d.pop("rules", [])
        fp = cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        fp.rules = [ConditionalRule.from_dict(r) for r in rules_data]
        return fp


@dataclass
class BadgeConfig:
    """Complete badge template: background, dimensions, fields, PDF options."""
    background_image_path: str = ""
    back_background_image_path: str = ""
    badge_width: int = 1050   # pixels (3.5" at 300 DPI)
    badge_height: int = 600   # pixels (2" at 300 DPI)
    fields: List[FieldPlacement] = field(default_factory=list)

    dpi: int = 300  # rendering DPI; font sizes are in points, scaled by dpi/72

    # PDF layout options
    badges_per_row: int = 2
    badges_per_col: int = 4
    page_size: str = "letter"  # "letter" or "A4"
    margin_mm: float = 10.0
    spacing_mm: float = 2.0

    def fields_for_side(self, side: str) -> List[FieldPlacement]:
        return [f for f in self.fields if f.side == side]

    @property
    def has_back(self) -> bool:
        return bool(self.back_background_image_path or self.fields_for_side("back"))


    def to_dict(self) -> dict:
        d = asdict(self)
        d["fields"] = [f.to_dict() for f in self.fields]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "BadgeConfig":
        d = dict(d)  # avoid mutating the input
        fields_data = d.pop("fields", [])
        config = cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        config.fields = [FieldPlacement.from_dict(f) for f in fields_data]
        return config

    def save_json(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_json(cls, path: str) -> "BadgeConfig":
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))
