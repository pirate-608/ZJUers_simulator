"""Tests for deterministic graduation fallback comments.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.
"""

from app.core import llm


def test_fallback_wenyan_report_uses_gpa_branches():
    """Graduation fallback text should vary by final cumulative GPA."""
    llm._GRADUATION_COMMENTS_CACHE = None

    assert "日夜勤勉" in llm.fallback_wenyan_report({"gpa": "4.6"})
    assert "仓廪殷实" in llm.fallback_wenyan_report({"gpa": "4.2"})
    assert "偶尔摸摸鱼" in llm.fallback_wenyan_report({"gpa": "3.8"})
    assert "一改前非" in llm.fallback_wenyan_report({"gpa": "3.2"})
