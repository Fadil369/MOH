from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
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


class PortalExtractionAuth(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    attempted: bool = False
    mode: str = ""
    likely_successful: bool = Field(default=False, alias="likelySuccessful")


class PortalExtractionEndpoints(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    urls: List[str] = Field(default_factory=list)
    process_urls: List[str] = Field(default_factory=list, alias="processUrls")
    ip_urls: List[str] = Field(default_factory=list, alias="ipUrls")
    relative_paths: List[str] = Field(default_factory=list, alias="relativePaths")
    ids: Dict[str, List[str]] = Field(default_factory=dict)


class PortalExtractionLink(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    text: str = ""
    href: str = ""
    absolute_url: str = Field(default="", alias="absoluteUrl")
    kind: str = "navigation"


class PortalExtractionForm(BaseModel):
    tag: str = ""
    type: str = ""
    name: str = ""
    id: str = ""
    placeholder: str = ""
    text: str = ""


class PortalExtractionTable(BaseModel):
    headers: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)
    row_count: int = Field(default=0, alias="rowCount")


class PortalExtractionRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    extraction_id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="extractionId")
    source: str
    portal_url: str = Field(default="", alias="portalUrl")
    current_url: str = Field(default="", alias="currentUrl")
    title: str = ""
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="capturedAt")
    auth: PortalExtractionAuth = Field(default_factory=PortalExtractionAuth)
    endpoints: PortalExtractionEndpoints = Field(default_factory=PortalExtractionEndpoints)
    links: List[PortalExtractionLink] = Field(default_factory=list)
    forms: List[PortalExtractionForm] = Field(default_factory=list)
    tables: List[PortalExtractionTable] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HITLRequest(BaseModel):
    claim_id: str
    amount_sar: float
    rejection_type: RejectionType
    recommended_action: NPHIESAction
    agent_assessments: dict = Field(default_factory=dict)


class IssueStatus(str, Enum):
    OPENED = "OPENED"
    CLOSED = "CLOSED"


class ClaimIssue(BaseModel):
    """Tracks an open/closed claim-rejection issue backed by a Google Chat space."""

    issue_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    space_id: str = ""
    subscription_id: str = ""
    status: IssueStatus = IssueStatus.OPENED
    resolution: str = ""
    report_url: str = ""
    claim_line_id: Optional[str] = None
