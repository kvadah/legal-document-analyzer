"""Portfolio report tests — generation, formats, RBAC, tenancy (09-api-spec.md §8)."""
import io
import json
import zipfile
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from tests.conftest import register_user

DOC = (
    b"Master Services Agreement\n\n"
    b"This Agreement is entered into between Acme Corp and Beta LLC.\n\n"
    b"The Client shall pay the Provider a total fee of $50,000 within 30 days of "
    b"receipt of invoice.\n\n"
    b"Each party shall keep all proprietary information strictly confidential and secure.\n\n"
    b"Either party may terminate this Agreement upon 30 days written notice.\n"
)


async def _upload(client, token, filename="msa.txt", content=DOC):
    resp = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", (filename, content, "text/plain"))],
    )
    assert resp.status_code == 202, resp.text
    return resp.json()["documents"][0]["document_id"]


async def _generate(client, token, payload):
    return await client.post(
        "/api/v1/reports",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )


async def _setup_org(client, email="reports@example.com", org_name="Reports Org"):
    reg = await register_user(client, email=email, org_name=org_name)
    return reg.json()["access_token"]


@pytest.mark.asyncio
async def test_portfolio_risk_report_generates_and_aggregates(client):
    token = await _setup_org(client)
    await _upload(client, token, "msa-1.txt", DOC)
    await _upload(client, token, "msa-2.txt", DOC.replace(b"$50,000", b"$75,000"))

    resp = await _generate(
        client, token, {"report_type": "portfolio_risk", "export_format": "json"}
    )
    assert resp.status_code == 202, resp.text
    report_id = resp.json()["report_id"]

    resp = await client.get(
        f"/api/v1/reports/{report_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "completed"
    assert body["report_type"] == "portfolio_risk"
    assert body["export_format"] == "json"

    # data is fetched through the download endpoint for json too
    dl = await client.get(
        f"/api/v1/reports/{report_id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dl.status_code == 200

    data = json.loads(dl.content)
    assert data["report_type"] == "portfolio_risk"
    assert data["scope"]["document_count"] == 2
    assert data["summary"]["documents_analyzed"] == 2
    assert set(data["risks_by_severity"]) == {"critical", "high", "medium", "low"}
    assert len(data["documents"]) == 2
    assert "disclaimer" in data and "not constitute legal advice" in data["disclaimer"]


@pytest.mark.asyncio
async def test_portfolio_risk_report_scoped_to_document_subset(client):
    token = await _setup_org(client, email="scoped@example.com", org_name="Scoped Org")
    doc_a = await _upload(client, token, "msa-1.txt", DOC)
    await _upload(client, token, "msa-2.txt", DOC.replace(b"$50,000", b"$75,000"))

    resp = await _generate(
        client,
        token,
        {
            "report_type": "portfolio_risk",
            "export_format": "json",
            "document_ids": [doc_a],
        },
    )
    report_id = resp.json()["report_id"]
    dl = await client.get(
        f"/api/v1/reports/{report_id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = json.loads(dl.content)
    assert data["scope"]["document_count"] == 1
    assert data["scope"]["filtered"] is True
    assert data["documents"][0]["document_id"] == doc_a


@pytest.mark.asyncio
async def test_obligation_calendar_report_generates(client):
    token = await _setup_org(client, email="cal@example.com", org_name="Cal Org")
    await _upload(client, token, "msa.txt")

    resp = await _generate(
        client, token, {"report_type": "obligation_calendar", "export_format": "json"}
    )
    assert resp.status_code == 202, resp.text
    report_id = resp.json()["report_id"]

    dl = await client.get(
        f"/api/v1/reports/{report_id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dl.status_code == 200

    data = json.loads(dl.content)
    assert data["report_type"] == "obligation_calendar"
    for section in ("overdue", "due_soon", "upcoming", "no_deadline", "completed"):
        assert section in data
    total = data["summary"]["total_obligations"]
    assert total == sum(len(data[s]) for s in ("overdue", "due_soon", "upcoming", "no_deadline", "completed"))
    # the payment clause produces at least one obligation
    assert total >= 1
    entry = (data["upcoming"] or data["no_deadline"])[0]
    assert entry["filename"] == "msa.txt"
    assert entry["obligated_party"]
    assert entry["deadline_type"]


@pytest.mark.asyncio
async def test_xlsx_report_downloads_as_valid_workbook(client):
    token = await _setup_org(client, email="xlsx@example.com", org_name="Xlsx Org")
    await _upload(client, token, "msa.txt")

    resp = await _generate(
        client, token, {"report_type": "portfolio_risk", "export_format": "xlsx"}
    )
    report_id = resp.json()["report_id"]

    dl = await client.get(
        f"/api/v1/reports/{report_id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dl.status_code == 200
    assert (
        dl.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "portfolio_risk-" in dl.headers["content-disposition"]

    archive = zipfile.ZipFile(io.BytesIO(dl.content))
    assert archive.testzip() is None
    names = archive.namelist()
    assert "[Content_Types].xml" in names
    assert "xl/workbook.xml" in names
    assert "xl/worksheets/sheet1.xml" in names
    sheet_names = archive.read("xl/workbook.xml").decode()
    assert "Summary" in sheet_names
    assert "Documents" in sheet_names


@pytest.mark.asyncio
async def test_pdf_and_docx_report_formats(client):
    for fmt in ("pdf", "docx"):
        token = await _setup_org(
            client, email=f"{fmt}@example.com", org_name=f"{fmt} Org"
        )
        await _upload(client, token, "msa.txt")
        resp = await _generate(
            client, token, {"report_type": "portfolio_risk", "export_format": fmt}
        )
        report_id = resp.json()["report_id"]
        dl = await client.get(
            f"/api/v1/reports/{report_id}/download",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert dl.status_code == 200, fmt
        if fmt == "pdf":
            assert dl.content.startswith(b"%PDF-")
        else:
            assert zipfile.ZipFile(io.BytesIO(dl.content)).testzip() is None


@pytest.mark.asyncio
async def test_report_list(client):
    token = await _setup_org(client, email="list@example.com", org_name="List Org")
    await _upload(client, token, "msa.txt")
    await _generate(client, token, {"report_type": "portfolio_risk"})
    await _generate(client, token, {"report_type": "obligation_calendar"})

    resp = await client.get(
        "/api/v1/reports",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert {r["report_type"] for r in body["reports"]} == {
        "portfolio_risk",
        "obligation_calendar",
    }
    # newest first
    assert body["reports"][0]["created_at"] >= body["reports"][1]["created_at"]


@pytest.mark.asyncio
async def test_report_requires_reviewer_role(client):
    reg = await register_user(client, email="rpt-viewer@example.com", org_name="Rpt Viewer Org")
    token = reg.json()["access_token"]
    invite = await client.post(
        "/api/v1/auth/invite",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "v2@example.com", "role": "viewer"},
    )
    assert invite.status_code in (200, 201), invite.text

    resp = await _generate(client, token, {"report_type": "portfolio_risk"})
    assert resp.status_code == 202  # admin can generate

    # viewers can list and read, but not generate
    resp = await client.get(
        "/api/v1/reports",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    report_id = resp.json()["reports"][0]["report_id"]
    resp = await client.get(
        f"/api/v1/reports/{report_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_report_org_isolation(client):
    token_a = await _setup_org(client, email="a@example.com", org_name="Org A")
    await _upload(client, token_a, "msa.txt")
    resp = await _generate(client, token_a, {"report_type": "portfolio_risk"})
    report_id = resp.json()["report_id"]

    reg_b = await register_user(client, email="b@example.com", org_name="Org B", password="password123")
    token_b = reg_b.json()["access_token"]

    # Org B cannot see Org A's report
    resp = await client.get(
        f"/api/v1/reports/{report_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404

    # Org B's portfolio report contains none of Org A's documents
    resp = await _generate(client, token_b, {"report_type": "portfolio_risk"})
    report_b = resp.json()["report_id"]
    dl = await client.get(
        f"/api/v1/reports/{report_b}/download",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    data = json.loads(dl.content)
    assert data["scope"]["document_count"] == 0
    assert data["documents"] == []


@pytest.mark.asyncio
async def test_report_unknown_document_rejected(client):
    token = await _setup_org(client, email="unknown@example.com", org_name="Unknown Org")
    resp = await _generate(
        client,
        token,
        {"report_type": "portfolio_risk", "document_ids": [str(uuid4())]},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_report_requires_analysis_ready(client, db_session):
    from sqlalchemy import select

    from app.models.models import Document, DocumentStatus

    token = await _setup_org(client, email="rpt-notready@example.com", org_name="Rpt NotReady Org")
    doc_id = await _upload(client, token, "msa.txt")

    # Force one document back to a pre-analysis status directly in the DB.
    result = await db_session.execute(
        select(Document).where(Document.id == UUID(doc_id))
    )
    doc = result.scalar_one()
    doc.status = DocumentStatus.UPLOADED
    await db_session.commit()

    resp = await _generate(
        client, token, {"report_type": "portfolio_risk", "document_ids": [doc_id]}
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "analysis_not_ready"


@pytest.mark.asyncio
async def test_download_rejected_before_completion(client, db_session):
    from app.models.models import Report, User

    token = await _setup_org(client, email="rpt-pending@example.com", org_name="Rpt Pending Org")

    result = await db_session.execute(
        select(User).where(User.email == "rpt-pending@example.com")
    )
    user = result.scalar_one()
    report = Report(
        id=uuid4(),
        organization_id=user.organization_id,
        generated_by=user.id,
        report_type="portfolio_risk",
        status="pending",
        export_format="json",
        document_ids=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(report)
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/reports/{report.id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "report_not_ready"


@pytest.mark.asyncio
async def test_report_requires_auth(client):
    resp = await client.post("/api/v1/reports", json={"report_type": "portfolio_risk"})
    assert resp.status_code == 401
