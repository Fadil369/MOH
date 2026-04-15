"""Tests for integrations/issue_store.py"""

import pytest
from integrations.issue_store import IssueStore
from core.models import ClaimIssue, IssueStatus


@pytest.fixture
def store():
    return IssueStore()


@pytest.fixture
def issue():
    return ClaimIssue(title="Test Issue", description="Desc", space_id="spaces/T1")


def test_save_and_get(store, issue):
    store.save(issue)
    retrieved = store.get("spaces/T1")
    assert retrieved is not None
    assert retrieved.title == "Test Issue"


def test_save_uses_issue_id_when_no_space(store):
    issue = ClaimIssue(title="No Space", description="d")
    store.save(issue)
    assert store.get(issue.issue_id) is not None


def test_close_marks_closed(store, issue):
    store.save(issue)
    updated = store.close("spaces/T1", "resolved", "https://docs/report")
    assert updated.status == IssueStatus.CLOSED
    assert updated.resolution == "resolved"
    assert updated.report_url == "https://docs/report"


def test_close_unknown_returns_none(store):
    result = store.close("spaces/UNKNOWN", "x", "y")
    assert result is None


def test_close_uses_unknown_when_resolution_empty(store, issue):
    store.save(issue)
    updated = store.close("spaces/T1", "", "url")
    assert updated.resolution == "Unknown"


def test_delete(store, issue):
    store.save(issue)
    store.delete("spaces/T1")
    assert store.get("spaces/T1") is None


def test_all_returns_all_issues(store):
    store.save(ClaimIssue(title="A", description="a", space_id="spaces/A"))
    store.save(ClaimIssue(title="B", description="b", space_id="spaces/B"))
    all_issues = store.all()
    assert len(all_issues) == 2


def test_all_empty(store):
    assert store.all() == []
