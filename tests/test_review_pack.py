"""The review pack's publish gate: matched months and cut-offs are published, anything else is refused."""
import sys

import pytest

from conftest import ROOT

sys.path.insert(0, str(ROOT / "src"))
from build_review_pack import reconcile  # noqa: E402


def test_matched_month_is_published(cur):
    status, diff, _ = reconcile(cur, "2026-03")
    assert status == "Matched" and abs(diff) <= 1


@pytest.mark.parametrize("month", ["2025-12", "2026-01"])
def test_cutoff_months_are_published_with_an_explanation(cur, month):
    status, diff, note = reconcile(cur, month)
    assert status == "Explained (cut-off)" and abs(diff) > 1e8 and "reverses" in note


def test_unexplained_difference_stops_the_pack(cur):
    cur.execute("UPDATE fi.gl_revenue SET revenue = revenue + 50000 WHERE fiscal_month = '2026-03' AND category = 'Fans'")
    with pytest.raises(SystemExit) as stop:
        reconcile(cur, "2026-03")
    assert "50,000" in str(stop.value)      # the change is rolled back after the test
