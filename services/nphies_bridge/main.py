import httpx
from fastapi import FastAPI, HTTPException
from core.models import FHIRBundle

app = FastAPI(title="NPHIES Bridge Service")

SUBMISSION_STORE = {}


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


bridge = NPHIESBridge()


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


@app.get("/health")
def health():
    return {"status": "ok", "service": "nphies_bridge"}
