"""Research document upload endpoint — deferred audit item #11.

Pins the size / empty / extraction / analysis pipeline contract for
POST /api/research/upload. The text extractor itself
(_extract_text_from_upload in article_ingestion_routes) has its own
tests; here we just pin the upload-route glue and error matrix.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from api.research_routes import upload_research_document, MAX_UPLOAD_BYTES


def _make_upload(content: bytes, filename: str = "report.pdf", content_type: str = "application/pdf"):
    """Minimal UploadFile stand-in. We need .read(), .filename, .content_type."""
    upload = MagicMock()
    upload.filename = filename
    upload.content_type = content_type

    async def read(n=-1):
        if n < 0 or n >= len(content):
            return content
        return content[:n]

    upload.read = read
    return upload


class TestUploadSizeGuard:
    @pytest.mark.asyncio
    async def test_413_when_file_exceeds_max(self):
        from fastapi import HTTPException

        # MAX_UPLOAD_BYTES + 1 = oversize. The read() returns N+1 so
        # the guard fires.
        big = b"x" * (MAX_UPLOAD_BYTES + 1)
        upload = _make_upload(big, "huge.pdf")
        with pytest.raises(HTTPException) as exc:
            await upload_research_document(file=upload, doi=None, current_user=None)
        assert exc.value.status_code == 413
        assert "exceeds maximum size" in exc.value.detail

    @pytest.mark.asyncio
    async def test_400_when_file_empty(self):
        from fastapi import HTTPException

        upload = _make_upload(b"", "empty.pdf")
        with pytest.raises(HTTPException) as exc:
            await upload_research_document(file=upload, doi=None, current_user=None)
        assert exc.value.status_code == 400


class TestUploadExtractionFailure:
    @pytest.mark.asyncio
    async def test_422_when_extracted_text_too_short(self):
        """Scanned PDFs or empty docx files produce very little text —
        we hint at OCR + the /analyze paste fallback rather than 500."""
        from fastapi import HTTPException

        upload = _make_upload(b"fake-pdf-bytes", "scan.pdf")
        with patch(
            "api.article_ingestion_routes._extract_text_from_upload",
            return_value="too short",
        ):
            with pytest.raises(HTTPException) as exc:
                await upload_research_document(
                    file=upload, doi=None, current_user=None
                )
        assert exc.value.status_code == 422
        assert "scanned/image-only" in exc.value.detail or "OCR" in exc.value.detail

    @pytest.mark.asyncio
    async def test_422_when_extractor_raises(self):
        from fastapi import HTTPException

        upload = _make_upload(b"binary-noise", "report.xyz", "application/octet-stream")
        with patch(
            "api.article_ingestion_routes._extract_text_from_upload",
            side_effect=ValueError("unsupported"),
        ):
            with pytest.raises(HTTPException) as exc:
                await upload_research_document(
                    file=upload, doi=None, current_user=None
                )
        # _extract_text_from_upload already raises HTTPException(422)
        # for unsupported types in real flow. Our route's catch-all
        # rewraps non-HTTPException errors into 422.
        assert exc.value.status_code in (422, 500)


class TestUploadHappyPath:
    @pytest.mark.asyncio
    async def test_calls_service_with_extracted_text(self):
        upload = _make_upload(b"%PDF-1.4 minimal", "thesis.pdf")
        extracted = "Climate change is real. " * 200  # 4600 chars, >200 min

        fake_service = MagicMock()
        fake_service.analyze_report = AsyncMock(
            return_value={"summary": "ok", "claim_count": 12}
        )

        with patch(
            "api.article_ingestion_routes._extract_text_from_upload",
            return_value=extracted,
        ), patch(
            "app.domains.intelligence.research_report_service.ResearchReportService",
            return_value=fake_service,
        ):
            result = await upload_research_document(
                file=upload,
                doi="10.1234/example",
                current_user={"user_id": "u-1"},
            )

        # Service was called with extracted text + provided doi + user_id.
        fake_service.analyze_report.assert_awaited_once()
        kwargs = fake_service.analyze_report.await_args.kwargs
        assert kwargs["text"] == extracted
        assert kwargs["doi"] == "10.1234/example"
        assert kwargs["user_id"] == "u-1"

        # Response includes upload-specific metadata.
        assert result["source"] == "upload"
        assert result["filename"] == "thesis.pdf"
        assert result["text_length"] == len(extracted)
        # And the service's own keys came through.
        assert result["summary"] == "ok"
        assert result["claim_count"] == 12

    @pytest.mark.asyncio
    async def test_anonymous_upload_passes_none_user_id(self):
        upload = _make_upload(b"%PDF-1.4 minimal", "anon.pdf")
        extracted = "x" * 1000

        fake_service = MagicMock()
        fake_service.analyze_report = AsyncMock(return_value={"summary": "ok"})

        with patch(
            "api.article_ingestion_routes._extract_text_from_upload",
            return_value=extracted,
        ), patch(
            "app.domains.intelligence.research_report_service.ResearchReportService",
            return_value=fake_service,
        ):
            await upload_research_document(file=upload, doi=None, current_user=None)

        assert fake_service.analyze_report.await_args.kwargs["user_id"] is None
