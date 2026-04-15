import pytest
import pandas as pd
import io
import os
from datetime import date
from services.normalizer.main import NormalizerService


@pytest.fixture
def normalizer():
    return NormalizerService()


@pytest.fixture
def moh187_csv(tmp_path):
    content = (
        "service_line_id,patient_id,provider_id,amount_sar,date_of_service\n"
        "SL-001,PAT-001,PROV-001,5000.0,2024-01-15\n"
        "SL-002,PAT-002,PROV-001,3000.0,2024-01-16\n"
    )
    f = tmp_path / "moh187.csv"
    f.write_text(content)
    return str(f)


@pytest.fixture
def claim_response_csv(tmp_path):
    content = (
        "service_line_id,rejection_code,status\n"
        "SL-001,SE-1-10,REJECTED\n"
        "SL-002,MN-1-1,REJECTED\n"
    )
    f = tmp_path / "claim_response.csv"
    f.write_text(content)
    return str(f)


@pytest.fixture
def gss_csv(tmp_path):
    content = "service_line_id,preauth_id\nSL-001,PA-001\nSL-002,PA-002\n"
    f = tmp_path / "gss.csv"
    f.write_text(content)
    return str(f)


def test_ingest_moh187(normalizer, moh187_csv):
    df = normalizer.ingest_moh187(moh187_csv)
    assert len(df) == 2
    assert "amount_sar" in df.columns
    assert df["amount_sar"].iloc[0] == 5000.0


def test_ingest_claim_response(normalizer, claim_response_csv):
    df = normalizer.ingest_claim_response(claim_response_csv)
    assert len(df) == 2
    assert "rejection_code" in df.columns


def test_ingest_gss(normalizer, gss_csv):
    df = normalizer.ingest_gss(gss_csv)
    assert len(df) == 2


def test_merge_sources(normalizer, moh187_csv, claim_response_csv, gss_csv):
    moh = normalizer.ingest_moh187(moh187_csv)
    resp = normalizer.ingest_claim_response(claim_response_csv)
    gss = normalizer.ingest_gss(gss_csv)
    merged = normalizer.merge_sources(moh, resp, gss)
    assert len(merged) == 2
    assert "rejection_code" in merged.columns


def test_to_claim_lines(normalizer, moh187_csv, claim_response_csv, gss_csv):
    moh = normalizer.ingest_moh187(moh187_csv)
    resp = normalizer.ingest_claim_response(claim_response_csv)
    gss = normalizer.ingest_gss(gss_csv)
    merged = normalizer.merge_sources(moh, resp, gss)
    claims = normalizer.to_claim_lines(merged)
    assert len(claims) == 2
    assert claims[0].amount_sar == 5000.0
    assert claims[0].rejection_code == "SE-1-10"


def test_missing_columns_raises(normalizer, tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("col1,col2\na,b\n")
    with pytest.raises(ValueError):
        normalizer.ingest_moh187(str(bad))
