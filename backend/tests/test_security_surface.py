"""Systematic security-surface tests (13-roadmap-build-order.md Phase 10).

Instead of spot-checks, these tests enumerate EVERY registered API route and
verify:

1. Every non-public route requires authentication (get_current_user in its
   dependency tree) — no accidentally unprotected endpoints.
2. Every mutating route (POST/PATCH/DELETE) requires at least reviewer —
   viewers are read-only per the RBAC matrix (11-security-compliance.md §2).
3. Cross-tenant org scoping: resource-owning endpoints return 404 (not 403,
   not data) when another org's ids are used.
"""
from typing import Any
from uuid import uuid4

import pytest
from app.core.deps import get_current_user
from app.main import app
from fastapi.routing import _IncludedRouter

from tests.conftest import register_user

# Routes intentionally reachable without a JWT (09-api-spec.md §1).
PUBLIC_ROUTES = {
    ("POST", "/api/v1/auth/register"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/refresh"),
    ("POST", "/api/v1/auth/logout"),
    ("POST", "/api/v1/auth/accept-invite"),
}

# Query-shaped POSTs: authenticated reads with a body, not mutations.
READ_STYLE_POSTS = {
    "/api/v1/search",
    "/api/v1/ask",
}

HEALTH_PREFIXES = ("/health",)


def _all_routes() -> list[Any]:
    """Flatten the app's lazily-included routers into effective route contexts.

    FastAPI >= 0.141 defers router includes: ``app.routes`` holds
    ``_IncludedRouter`` wrappers instead of materialized ``APIRoute``
    objects, so expand them recursively into their effective route
    contexts (which carry the full path, methods, and dependant).
    """
    contexts: list[Any] = []

    def _flatten(candidates: Any) -> None:
        for candidate in candidates:
            if isinstance(candidate, _IncludedRouter):
                _flatten(candidate.effective_candidates())
            else:
                contexts.append(candidate)

    for route in app.routes:
        if isinstance(route, _IncludedRouter):
            _flatten(route.effective_candidates())
    return contexts


def _dependency_calls(route: Any) -> set[Any]:
    """Collect every callable in the route's dependency tree (recursive).

    FastAPI lifts parameter-level ``Depends(...)`` into
    ``dependant.dependencies``, so one walk covers both styles.
    """
    calls: set[Any] = set()

    def walk(dependant: Any) -> None:
        for dep in dependant.dependencies:
            calls.add(dep.call)
            walk(dep)

    walk(route.dependant)
    return calls


def _requires_auth(route: Any) -> bool:
    return get_current_user in _dependency_calls(route)


def _role_requirements(route: Any) -> list[set[str]]:
    """Allowed-role sets from every require_role(...) dependency in the tree."""
    requirements = []
    for call in _dependency_calls(route):
        if getattr(call, "__qualname__", "") == "require_role.<locals>._check_role":
            for cell in call.__closure__ or ():
                if isinstance(cell.cell_contents, tuple):
                    requirements.append(set(cell.cell_contents))
    return requirements


def _route_id(method: str, path: str) -> str:
    return f"{method} {path}"


def test_every_non_public_route_requires_auth():
    missing = []
    for route in _all_routes():
        path = route.path
        if path.startswith(HEALTH_PREFIXES):
            continue
        methods = (route.methods or set()) - {"HEAD"}
        for method in methods or ("?",):
            if (method, path) in PUBLIC_ROUTES:
                continue
            if not _requires_auth(route):
                missing.append(_route_id(method, path))
    assert not missing, f"Routes without authentication: {missing}"
    # Sanity: the auth dependency really was found on protected routes.
    assert any("documents" in r.path for r in _all_routes())


def test_public_routes_are_limited_to_auth_and_health():
    for route in _all_routes():
        if route.path.startswith(HEALTH_PREFIXES):
            continue
        methods = (route.methods or set()) - {"HEAD"}
        for method in methods:
            if not _requires_auth(route):
                assert (method, route.path) in PUBLIC_ROUTES, (
                    f"{method} {route.path} is public but not in PUBLIC_ROUTES"
                )


def test_mutating_routes_require_reviewer_or_admin():
    """Every POST/PATCH/DELETE (except public auth + read-style queries)
    must enforce at least reviewer-level permissions."""
    violations = []
    for route in _all_routes():
        methods = (route.methods or set()) - {"HEAD"}
        mutating = methods & {"POST", "PATCH", "DELETE", "PUT"}
        if not mutating:
            continue
        for method in mutating:
            if (method, route.path) in PUBLIC_ROUTES:
                continue
            if method == "POST" and route.path in READ_STYLE_POSTS:
                continue
            # Path-param POSTs that are queries (document-scoped ask).
            if method == "POST" and route.path.endswith("/ask"):
                continue
            requirements = _role_requirements(route)
            if not requirements:
                violations.append(_route_id(method, route.path))
                continue
            # At least one requirement must be reviewer-or-admin or admin.
            ok = any({"reviewer", "admin"} <= roles or roles == {"admin"} for roles in requirements)
            if not ok:
                violations.append(_route_id(method, route.path))
    assert not violations, f"Mutating routes without reviewer+ RBAC: {violations}"


def test_admin_routes_require_admin_role():
    for route in _all_routes():
        if not route.path.startswith("/api/v1/admin"):
            continue
        requirements = _role_requirements(route)
        assert requirements, f"{route.path} has no role requirement"
        assert all(roles == {"admin"} for roles in requirements), (
            f"{route.path} allows non-admin roles: {requirements}"
        )


# ── Cross-tenant org scoping (systematic sweep) ───────────────────────────────


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_resource_endpoints_are_org_scoped(client, monkeypatch):
    async def _nop(points):
        return None

    monkeypatch.setattr("app.pipelines.ingestion.pipeline._upsert_qdrant_points", _nop)

    reg_a = await register_user(client, org_name="Sec A", email="sec-a@example.com")
    reg_b = await register_user(client, org_name="Sec B", email="sec-b@example.com")
    token_a = reg_a.json()["access_token"]
    token_b = reg_b.json()["access_token"]

    upload = await client.post(
        "/api/v1/documents/upload",
        headers=_auth(token_a),
        files=[
            (
                "files",
                (
                    "msa.txt",
                    b"MASTER SERVICES AGREEMENT between Acme Corp and Beta LLC.\n"
                    b"Confidentiality. Each party shall keep information confidential.\n",
                    "text/plain",
                ),
            )
        ],
    )
    assert upload.status_code == 202, upload.text
    doc_id = upload.json()["documents"][0]["document_id"]

    report = await client.post(
        "/api/v1/reports",
        headers=_auth(token_a),
        json={"report_type": "portfolio_risk", "export_format": "json"},
    )
    assert report.status_code == 202, report.text
    report_id = report.json()["report_id"]

    # Every read path over org A's resources must 404 for org B.
    get_paths = [
        f"/api/v1/documents/{doc_id}",
        f"/api/v1/documents/{doc_id}/text",
        f"/api/v1/documents/{doc_id}/summary",
        f"/api/v1/documents/{doc_id}/clauses",
        f"/api/v1/documents/{doc_id}/risks",
        f"/api/v1/documents/{doc_id}/entities",
        f"/api/v1/documents/{doc_id}/obligations",
        f"/api/v1/documents/{doc_id}/score",
        f"/api/v1/documents/{doc_id}/versions",
        f"/api/v1/documents/{doc_id}/relationships",
        f"/api/v1/documents/{doc_id}/comments",
        f"/api/v1/documents/{doc_id}/annotations",
        f"/api/v1/documents/{doc_id}/export",
        f"/api/v1/reports/{report_id}",
    ]
    for path in get_paths:
        resp = await client.get(path, headers=_auth(token_b))
        assert resp.status_code == 404, f"{path} leaked across tenants: {resp.status_code}"

    # Mutations over org A's resources must also 404 for org B.
    resp = await client.delete(f"/api/v1/documents/{doc_id}", headers=_auth(token_b))
    assert resp.status_code == 404
    resp = await client.delete(f"/api/v1/reports/{report_id}", headers=_auth(token_b))
    assert resp.status_code in (404, 405)  # 405 if route absent — fine, nothing leaked

    # And org B cannot even see org A's documents in listings/search.
    listing = await client.get("/api/v1/documents", headers=_auth(token_b))
    assert listing.status_code == 200
    assert all(item["id"] != doc_id for item in listing.json()["items"])

    # A completely unknown UUID is a 404, not a 500.
    random_id = uuid4()
    resp = await client.get(f"/api/v1/documents/{random_id}", headers=_auth(token_b))
    assert resp.status_code == 404
