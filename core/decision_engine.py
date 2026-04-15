from typing import List
from core.models import ClaimLine, NPHIESAction, RejectionType, HITLRequest

HITL_THRESHOLD = 10_000.0


class DecisionEngine:
    def route_claim(self, claim: ClaimLine, agent_outputs: dict = None) -> NPHIESAction:
        agent_outputs = agent_outputs or {}
        if claim.rejection_type == RejectionType.ADMINISTRATIVE:
            return NPHIESAction.RESUBMIT_NEW
        elif claim.rejection_type == RejectionType.CLINICAL_DOCUMENTATION:
            return NPHIESAction.APPEAL
        elif claim.rejection_type == RejectionType.PREAUTHORIZATION:
            code = claim.rejection_code or ""
            if code.startswith("BE-1-4"):
                return NPHIESAction.RESUBMIT_NEW
            return NPHIESAction.APPEAL
        elif claim.rejection_type == RejectionType.MEDICATION_DEVICE:
            return NPHIESAction.APPEAL
        elif claim.rejection_type == RejectionType.POLICY_LIMITATION:
            fraud_score = agent_outputs.get("fraud_score", 0.0)
            if fraud_score > 0.7:
                return NPHIESAction.VOID
            return NPHIESAction.APPEAL
        return NPHIESAction.RESUBMIT_NEW

    def should_trigger_hitl(self, claim: ClaimLine) -> bool:
        return claim.amount_sar > HITL_THRESHOLD

    def batch_route(self, claims: List[ClaimLine], agent_outputs: dict = None) -> dict:
        agent_outputs = agent_outputs or {}
        return {
            claim.service_line_id: self.route_claim(
                claim, agent_outputs.get(claim.service_line_id, {})
            )
            for claim in claims
        }

    def build_hitl_request(
        self, claim: ClaimLine, action: NPHIESAction, agent_assessments: dict
    ) -> HITLRequest:
        return HITLRequest(
            claim_id=claim.service_line_id,
            amount_sar=claim.amount_sar,
            rejection_type=claim.rejection_type or RejectionType.ADMINISTRATIVE,
            recommended_action=action,
            agent_assessments=agent_assessments,
        )
