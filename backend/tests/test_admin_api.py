"""Integration tests for the Phase 5 administrative HTTP contract."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.knowledge import KnowledgeHubService
from backend.api.runtime import ProviderRuntimeStore
from backend.config.settings import AppSettings


def test_admin_api_hides_credentials_and_accepts_safe_document_upload(tmp_path: Path) -> None:
    """The browser sees safe provider status and can index a tenant document."""
    settings = AppSettings(chroma_persist_dir=str(tmp_path / "chroma"))
    runtime = ProviderRuntimeStore(settings, state_path=tmp_path / "provider-runtime.json")
    knowledge_hub = KnowledgeHubService(settings, data_dir=tmp_path / "knowledge")

    with (
        patch("backend.api.routes.admin.get_provider_runtime_store", return_value=runtime),
        patch("backend.api.routes.admin.get_knowledge_hub", return_value=knowledge_hub),
    ):
        client = TestClient(create_app())
        providers = client.get("/api/v1/admin/providers")
        upload = client.post(
            "/api/v1/admin/knowledge/upload",
            data={"tenant_id": "grand-meridian"},
            files={"document": ("arrival.md", b"Check-in begins at 3 PM.", "text/markdown")},
        )

    assert providers.status_code == 200
    assert "api_key" not in providers.text
    assert upload.status_code == 200
    assert upload.json()["chunks_indexed"] == 1
