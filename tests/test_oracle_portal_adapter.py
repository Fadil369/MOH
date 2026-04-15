import pytest

from integrations.oracle_portal_adapter import (
    BranchSafeOraclePortalAdapter,
    OraclePortalPolicyConfig,
)


@pytest.mark.asyncio
async def test_submit_appeal_defaults_to_dry_run_guardrail():
    calls = []

    async def fake_invoker(tool_name, arguments):
        calls.append((tool_name, arguments))
        return {"ok": True}

    adapter = BranchSafeOraclePortalAdapter(
        invoker=fake_invoker,
        policy=OraclePortalPolicyConfig(
            default_branch="abha",
            allowed_branches={"abha", "riyadh"},
            allow_live_submit=False,
        ),
    )

    with pytest.raises(PermissionError):
        await adapter.submit_appeal(
            invoice_no="2816630",
            appeal_message="Please re-adjudicate claim",
            branch="riyadh",
            dry_run=False,
        )

    assert calls == []


@pytest.mark.asyncio
async def test_submit_appeal_passes_branch_and_dry_run():
    calls = []

    async def fake_invoker(tool_name, arguments):
        calls.append((tool_name, arguments))
        return {"status": "READY_TO_SUBMIT"}

    adapter = BranchSafeOraclePortalAdapter(
        invoker=fake_invoker,
        policy=OraclePortalPolicyConfig(
            default_branch="abha",
            allowed_branches={"abha", "riyadh"},
            allow_live_submit=False,
        ),
    )

    result = await adapter.submit_appeal(
        invoice_no="2816630",
        appeal_message="Please re-adjudicate claim",
        branch="riyadh",
        dry_run=True,
    )

    assert result["status"] == "READY_TO_SUBMIT"
    assert calls[0][0] == "portal_submit_appeal"
    assert calls[0][1]["branch"] == "riyadh"
    assert calls[0][1]["dryRun"] is True


@pytest.mark.asyncio
async def test_invalid_branch_is_blocked():
    async def fake_invoker(tool_name, arguments):
        return {"ok": True}

    adapter = BranchSafeOraclePortalAdapter(
        invoker=fake_invoker,
        policy=OraclePortalPolicyConfig(
            default_branch="abha",
            allowed_branches={"abha", "riyadh"},
            allow_live_submit=True,
        ),
    )

    with pytest.raises(ValueError):
        await adapter.get_claims(branch="jeddah")
