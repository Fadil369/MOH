import pandas as pd
from typing import List
from datetime import date
from fastapi import FastAPI, UploadFile, HTTPException
import io
from core.models import ClaimLine, ClaimStatus, RejectionType

app = FastAPI(title="Normalizer Service")


class NormalizerService:
    def ingest_moh187(self, filepath: str) -> pd.DataFrame:
        df = pd.read_csv(filepath)
        df.columns = [c.lower().strip().replace(" ", "_") for c in df.columns]
        required = {"service_line_id", "patient_id", "provider_id", "amount_sar", "date_of_service"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"MOH-187 missing columns: {missing}")
        df["amount_sar"] = pd.to_numeric(df["amount_sar"], errors="coerce").fillna(0.0)
        df["date_of_service"] = pd.to_datetime(df["date_of_service"], errors="coerce").dt.date
        return df

    def ingest_claim_response(self, filepath: str) -> pd.DataFrame:
        df = pd.read_csv(filepath)
        df.columns = [c.lower().strip().replace(" ", "_") for c in df.columns]
        if "rejection_code" in df.columns:
            df["rejection_code"] = df["rejection_code"].astype(str).str.strip()
        return df

    def ingest_gss(self, filepath: str) -> pd.DataFrame:
        df = pd.read_csv(filepath)
        df.columns = [c.lower().strip().replace(" ", "_") for c in df.columns]
        return df

    def merge_sources(
        self,
        moh187_df: pd.DataFrame,
        claim_response_df: pd.DataFrame,
        gss_df: pd.DataFrame,
    ) -> pd.DataFrame:
        merged = moh187_df

        if "service_line_id" in claim_response_df.columns or "claim_id" in claim_response_df.columns:
            claim_response_col = (
                "service_line_id"
                if "service_line_id" in claim_response_df.columns
                else "claim_id"
            )
            merged = merged.merge(
                claim_response_df,
                left_on="service_line_id",
                right_on=claim_response_col,
                how="left",
                suffixes=("", "_resp"),
            )

        if "service_line_id" in gss_df.columns or "claim_id" in gss_df.columns:
            gss_col = (
                "service_line_id" if "service_line_id" in gss_df.columns else "claim_id"
            )
            merged = merged.merge(
                gss_df,
                left_on="service_line_id",
                right_on=gss_col,
                how="left",
                suffixes=("", "_gss"),
            )
        return merged

    def to_claim_lines(self, df: pd.DataFrame) -> List[ClaimLine]:
        claims = []
        for _, row in df.iterrows():
            dos = row.get("date_of_service")
            if dos is None or (isinstance(dos, float) and pd.isna(dos)):
                dos = date.today()
            if not isinstance(dos, date):
                try:
                    dos = pd.to_datetime(dos).date()
                except Exception:
                    dos = date.today()

            rejection_code_raw = row.get("rejection_code")
            rejection_code = (
                str(rejection_code_raw).strip()
                if rejection_code_raw is not None and not (
                    isinstance(rejection_code_raw, float) and pd.isna(rejection_code_raw)
                )
                else None
            )
            if rejection_code in ("nan", "None", ""):
                rejection_code = None

            preauth_raw = row.get("preauth_id", None)
            preauth_id = (
                str(preauth_raw)
                if preauth_raw is not None and not (
                    isinstance(preauth_raw, float) and pd.isna(preauth_raw)
                )
                else None
            )

            med_raw = row.get("medication_code", None)
            medication_code = (
                str(med_raw)
                if med_raw is not None and not (
                    isinstance(med_raw, float) and pd.isna(med_raw)
                )
                else None
            )

            claims.append(
                ClaimLine(
                    service_line_id=str(row.get("service_line_id", "")),
                    patient_id=str(row.get("patient_id", "UNKNOWN")),
                    provider_id=str(row.get("provider_id", "UNKNOWN")),
                    amount_sar=float(row.get("amount_sar", 0.0)),
                    rejection_code=rejection_code,
                    date_of_service=dos,
                    preauth_id=preauth_id,
                    medication_code=medication_code,
                )
            )
        return claims


normalizer = NormalizerService()


@app.post("/ingest")
async def ingest(file: UploadFile):
    content = await file.read()
    df = pd.read_csv(io.StringIO(content.decode()))
    return {"rows": len(df), "columns": list(df.columns)}


@app.get("/health")
def health():
    return {"status": "ok", "service": "normalizer"}
