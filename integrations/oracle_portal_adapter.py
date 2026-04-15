from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol

import httpx


class OraclePortalToolInvoker(Protocol):
    async def __call__(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class OraclePortalPolicyConfig:
    default_branch: str
    allowed_branches: set[str]
    allow_live_submit: bool

    @classmethod
    def from_env(cls) -> "OraclePortalPolicyConfig":
        default_branch = os.getenv("ORACLE_PORTAL_DEFAULT_BRANCH", "abha").strip() or "abha"
        allowed = os.getenv("ORACLE_PORTAL_ALLOWED_BRANCHES", "abha,riyadh")
        allowed_branches = {part.strip() for part in allowed.split(",") if part.strip()}
        if not allowed_branches:
            allowed_branches = {default_branch}
        allow_live_submit = os.getenv("ORACLE_PORTAL_ALLOW_LIVE_SUBMIT", "false").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        return cls(
            default_branch=default_branch,
            allowed_branches=allowed_branches,
            allow_live_submit=allow_live_submit,
        )


class HttpOraclePortalToolInvoker:
    """HTTP invoker for MCP bridge endpoints.

    Expected endpoint accepts JSON payload:
      {"tool": "portal_get_claims", "arguments": {...}}
    and returns JSON result payload.
    """

    def __init__(self, endpoint: str, timeout_seconds: float = 30.0):
        self.endpoint = endpoint.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def __call__(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = {"tool": tool_name, "arguments": arguments}
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(self.endpoint, json=payload)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("Invalid MCP bridge response format")
            return data


class BranchSafeOraclePortalAdapter:
    """Branch-safe adapter for oracle-portal MCP tools with dry-run guardrails."""

    def __init__(
        self,
        invoker: OraclePortalToolInvoker,
        policy: OraclePortalPolicyConfig | None = None,
    ) -> None:
        self.invoker = invoker
        self.policy = policy or OraclePortalPolicyConfig.from_env()

    def _resolve_branch(self, branch: str | None) -> str:
        resolved = (branch or self.policy.default_branch).strip().lower()
        if resolved not in self.policy.allowed_branches:
            allowed = ", ".join(sorted(self.policy.allowed_branches))
            raise ValueError(f"Unsupported branch '{resolved}'. Allowed branches: {allowed}")
        return resolved

    def _enforce_submit_policy(self, dry_run: bool) -> None:
        if not dry_run and not self.policy.allow_live_submit:
            raise PermissionError(
                "Live submit is disabled by ORACLE_PORTAL_ALLOW_LIVE_SUBMIT=false. "
                "Use dry_run=True or explicitly enable live submit in environment policy."
            )

    async def list_branches(self) -> dict[str, Any]:
        return await self.invoker("portal_list_branches", {})

    async def search_patient(
        self,
        mrn: str | None = None,
        name: str | None = None,
        invoice_no: str | None = None,
        branch: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "branch": self._resolve_branch(branch),
            "mrn": mrn,
            "name": name,
            "invoiceNo": invoice_no,
        }
        return await self.invoker("portal_search_patient", payload)

    async def get_claims(
        self,
        invoice_no: str | None = None,
        status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        payer: str | None = None,
        max_results: int = 50,
        branch: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "branch": self._resolve_branch(branch),
            "invoiceNo": invoice_no,
            "status": status,
            "dateFrom": date_from,
            "dateTo": date_to,
            "payer": payer,
            "maxResults": max_results,
        }
        return await self.invoker("portal_get_claims", payload)

    async def submit_appeal(
        self,
        invoice_no: str,
        appeal_message: str,
        branch: str | None = None,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        self._enforce_submit_policy(dry_run)
        payload = {
            "branch": self._resolve_branch(branch),
            "invoiceNo": invoice_no,
            "appealMessage": appeal_message,
            "dryRun": dry_run,
        }
        return await self.invoker("portal_submit_appeal", payload)


def build_adapter_from_env(
    custom_invoker: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]] | None = None,
) -> BranchSafeOraclePortalAdapter:
    if custom_invoker is not None:
        return BranchSafeOraclePortalAdapter(custom_invoker)

    endpoint = os.getenv("ORACLE_PORTAL_MCP_ENDPOINT", "").strip()
    if not endpoint:
        raise ValueError(
            "ORACLE_PORTAL_MCP_ENDPOINT is not set. Configure it or pass a custom invoker."
        )

    invoker = HttpOraclePortalToolInvoker(endpoint=endpoint)
    return BranchSafeOraclePortalAdapter(invoker)
