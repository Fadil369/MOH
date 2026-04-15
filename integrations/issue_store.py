"""In-memory store for ClaimIssue objects, mirroring Apps Script PropertiesService."""

from typing import Dict, Optional
from core.models import ClaimIssue, IssueStatus


class IssueStore:
    """Thread-safe-enough in-memory store; can be replaced by a persistent backend."""

    def __init__(self) -> None:
        self._store: Dict[str, ClaimIssue] = {}

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def save(self, issue: ClaimIssue) -> ClaimIssue:
        """Persist (create or update) an issue keyed by space_id."""
        key = issue.space_id or issue.issue_id
        self._store[key] = issue
        return issue

    def close(
        self, space_id: str, resolution: str, report_url: str
    ) -> Optional[ClaimIssue]:
        """Mark an issue CLOSED and record its resolution & report URL."""
        issue = self._store.get(space_id)
        if issue is None:
            return None
        updated = issue.model_copy(
            update={
                "status": IssueStatus.CLOSED,
                "resolution": resolution or "Unknown",
                "report_url": report_url,
            }
        )
        self._store[space_id] = updated
        return updated

    def delete(self, space_id: str) -> None:
        self._store.pop(space_id, None)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get(self, space_id: str) -> Optional[ClaimIssue]:
        return self._store.get(space_id)

    def all(self) -> list[ClaimIssue]:
        return list(self._store.values())


# Module-level singleton – imported by google_chat_bot and workspace_events.
issue_store = IssueStore()
