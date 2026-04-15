from pydantic import BaseModel, Field, model_validator
from typing import List, Optional
from enum import Enum
from datetime import date, datetime, timezone
import uuid


class RejectionType(str, Enum):
    ADMINISTRATIVE = "ADMINISTRATIVE"
    CLINICAL_DOCUMENTATION = "CLINICAL_DOCUMENTATION"
    PREAUTHORIZATION = "PREAUTHORIZATION"
    MEDICATION_DEVICE = "MEDICATION_DEVICE"
    POLICY_LIMITATION = "POLICY_LIMITATION"


class NPHIESAction(str, Enum):
    APPEAL = "APPEAL"
    RESUBMIT_NEW = "RESUBMIT_NEW"
    CANCEL = "CANCEL"
    VOID = "VOID"


class ClaimStatus(str, Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    REJECTED = "REJECTED"
    APPEALED = "APPEALED"
    APPROVED = "APPROVED"


class ClaimLine(BaseModel):
    service_line_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    patient_id: str
    provider_id: str
    amount_sar: float = Field(ge=0)
    rejection_code: Optional[str] = None
    rejection_type: Optional[RejectionType] = None
    date_of_service: date
    status: ClaimStatus = ClaimStatus.PENDING
    preauth_id: Optional[str] = None
    medication_code: Optional[str] = None


class ClaimResponse(BaseModel):
    claim_id: str
    service_lines: List[ClaimLine]
    total_amount: float
    status: ClaimStatus


class FHIRBundle(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resourceType: str = "Bundle"
    type: str
    entry: List[dict] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HITLRequest(BaseModel):
    claim_id: str
    amount_sar: float
    rejection_type: RejectionType
    recommended_action: NPHIESAction
    agent_assessments: dict = Field(default_factory=dict)
