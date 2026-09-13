"""WCAG contrast checks for the frontend palette.

03-UIUX-RULES.md requires palette contrast to be checked explicitly rather than eyeballed.
Parsing the real CSS tokens means any palette edit that breaks contrast fails the test suite.
"""

import re

import pytest

from meridian.config import PROJECT_ROOT

TOKENS_CSS = PROJECT_ROOT / "frontend" / "src" / "app" / "globals.css"
AA_NORMAL_TEXT = 4.5

# (foreground token, background token) for every pairing the UI uses to render text.
TEXT_PAIRS = [
    ("--color-text", "--color-canvas"),
    ("--color-text", "--color-surface"),
    ("--color-text", "--color-surface-sunken"),
    ("--color-text-muted", "--color-canvas"),
    ("--color-text-muted", "--color-surface"),
    ("--color-text-muted", "--color-surface-sunken"),
    ("--color-accent", "--color-canvas"),
    ("--color-accent", "--color-surface"),
    ("--color-accent", "--color-accent-soft"),
    ("--color-text-inverse", "--color-accent"),
    ("--color-risk-high", "--color-risk-high-soft"),
    ("--color-risk-medium", "--color-risk-medium-soft"),
    ("--color-risk-low", "--color-risk-low-soft"),
    ("--color-risk-high", "--color-surface"),
    ("--color-risk-medium", "--color-surface"),
    ("--color-risk-low", "--color-surface"),
]


def _load_tokens() -> dict[str, str]:
    """Read `--color-name: #rrggbb;` declarations from the stylesheet."""
    css = TOKENS_CSS.read_text()
    pattern = r"(--color-[\w-]+):\s*(#[0-9a-fA-F]{6})\s*;"
    return {name: value.lower() for name, value in re.findall(pattern, css)}


def _relative_luminance(hex_color: str) -> float:
    """WCAG 2.x relative luminance of an sRGB hex colour."""
    channels = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG contrast ratio between two hex colours, from 1.0 to 21.0."""
    lighter, darker = sorted(
        (_relative_luminance(foreground), _relative_luminance(background)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


def test_contrast_formula_matches_reference_values() -> None:
    """Anchor the formula to published values so a broken implementation cannot pass every pair."""
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0)
    assert contrast_ratio("#777777", "#ffffff") == pytest.approx(4.48, abs=0.01)


AA_NON_TEXT = 3.0

# Graphical marks a reader must perceive to understand a chart or map (WCAG 1.4.11).
NON_TEXT_PAIRS = [
    ("--color-edge", "--color-canvas"),
    ("--color-edge", "--color-surface"),
    ("--color-accent", "--color-surface-sunken"),
]


@pytest.mark.parametrize(("foreground", "background"), NON_TEXT_PAIRS)
def test_graphic_marks_meet_non_text_contrast(foreground: str, background: str) -> None:
    """Edges, bars and axes must reach 3:1 against their background (WCAG AA, non-text)."""
    tokens = _load_tokens()

    ratio = contrast_ratio(tokens[foreground], tokens[background])

    assert ratio >= AA_NON_TEXT, f"{foreground} on {background} is only {ratio:.2f}:1"


@pytest.mark.parametrize(("foreground", "background"), TEXT_PAIRS)
def test_text_pairs_meet_wcag_aa(foreground: str, background: str) -> None:
    """Every text/background pairing must reach 4.5:1 (WCAG AA for normal-size text)."""
    tokens = _load_tokens()

    ratio = contrast_ratio(tokens[foreground], tokens[background])

    assert ratio >= AA_NORMAL_TEXT, f"{foreground} on {background} is only {ratio:.2f}:1"
