import httpx
import os
from fastapi import FastAPI, HTTPException
from core.models import FHIRBundle, PortalExtractionRecord

app = FastAPI(title="NPHIES Bridge Service")

SUBMISSION_STORE = {}
PORTAL_EXTRACTION_STORE = {}
PORTAL_EXTRACTION_FORWARD_TIMEOUT_SEC = 20.0


async def _forward_portal_extraction(record: dict) -> dict:
    webhook = os.getenv("N8N_PORTAL_EXTRACTION_WEBHOOK_URL", "").strip()
    if not webhook:
        return {"forwarded": False, "reason": "webhook-not-configured"}

    payload = {
        "eventType": "portal.extraction.received",
        "capturedAt": record.get("capturedAt"),
        "source": record.get("source"),
        "extraction": record,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                webhook,
                json=payload,
                timeout=PORTAL_EXTRACTION_FORWARD_TIMEOUT_SEC,
            )
            response.raise_for_status()
            return {
                "forwarded": True,
                "statusCode": response.status_code,
                "target": "n8n",
            }
    except httpx.HTTPError as exc:
        return {
            "forwarded": False,
            "reason": "http-error",
            "error": str(exc),
            "target": "n8n",
        }


class NPHIESBridge:
    def __init__(self, nphies_url: str = "https://nphies.sa/api"):
        self.nphies_url = nphies_url

    async def submit_claim(self, bundle: FHIRBundle, nphies_url: str = None) -> dict:
        url = nphies_url or self.nphies_url
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{url}/claim",
                json=bundle.model_dump(mode="json"),
                headers={"Content-Type": "application/fhir+json"},
                timeout=30.0,
            )
            resp.raise_for_status()
            result = resp.json()
            SUBMISSION_STORE[bundle.id] = {"status": "submitted", "response": result}
            return result

    async def submit_appeal(self, bundle: FHIRBundle) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.nphies_url}/appeal",
                json=bundle.model_dump(mode="json"),
                headers={"Content-Type": "application/fhir+json"},
                timeout=30.0,
            )
            resp.raise_for_status()
            result = resp.json()
            SUBMISSION_STORE[bundle.id] = {"status": "appealed", "response": result}
            return result

    async def check_status(self, claim_id: str) -> dict:
        if claim_id in SUBMISSION_STORE:
            return SUBMISSION_STORE[claim_id]
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.nphies_url}/claim/{claim_id}",
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()


bridge = NPHIESBridge(nphies_url=os.getenv("NPHIES_API_URL", "https://nphies.sa/api"))


@app.post("/submit")
async def submit(bundle: FHIRBundle):
    try:
        result = await bridge.submit_claim(bundle)
        return result
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/status/{claim_id}")
async def status(claim_id: str):
    return await bridge.check_status(claim_id)


@app.post("/portal-extractions")
async def ingest_portal_extraction(record: PortalExtractionRecord):
    payload = record.model_dump(mode="json", by_alias=True)
    PORTAL_EXTRACTION_STORE[record.extraction_id] = payload
    downstream = await _forward_portal_extraction(payload)
    return {
        "status": "stored",
        "extractionId": record.extraction_id,
        "source": record.source,
        "capturedAt": payload["capturedAt"],
        "downstream": downstream,
    }


@app.get("/portal-extractions")
def list_portal_extractions(source: str | None = None):
    items = list(PORTAL_EXTRACTION_STORE.values())
    if source:
        items = [item for item in items if str(item.get("source", "")).lower() == source.lower()]
    return {
        "count": len(items),
        "items": items,
    }


@app.get("/portal-extractions/{extraction_id}")
def get_portal_extraction(extraction_id: str):
    record = PORTAL_EXTRACTION_STORE.get(extraction_id)
    if not record:
        raise HTTPException(status_code=404, detail="Portal extraction not found")
    return record


@app.get("/health")
def health():
    return {"status": "ok", "service": "nphies_bridge"}
