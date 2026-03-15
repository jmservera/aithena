from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Set test environment variables before importing main
os.environ["UPLOAD_DIR"] = "/tmp/test_uploads"
os.environ["MAX_UPLOAD_SIZE_MB"] = "50"
os.environ["RABBITMQ_QUEUE_NAME"] = "shortembeddings"

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def valid_pdf_content() -> bytes:
    """Return minimal valid PDF content."""
    return b"%PDF-1.4\n%\xE2\xE3\xCF\xD3\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"


@pytest.fixture
def mock_rabbitmq():
    """Mock RabbitMQ connection and channel."""
    with patch("main.pika.BlockingConnection") as mock_conn:
        mock_channel = MagicMock()
        mock_connection = MagicMock()
        mock_connection.channel.return_value = mock_channel
        mock_conn.return_value = mock_connection
        yield mock_channel


@pytest.fixture
def upload_dir(tmp_path):
    """Use a temporary upload directory for tests."""
    from config import settings
    upload_path = tmp_path / "uploads"
    upload_path.mkdir(exist_ok=True)
    # Replace the upload_dir in settings by using object.__setattr__ on frozen dataclass
    object.__setattr__(settings, "upload_dir", upload_path)
    yield upload_path
    # Cleanup
    import shutil
    if upload_path.exists():
        shutil.rmtree(upload_path)


def test_upload_valid_pdf(client: TestClient, valid_pdf_content: bytes, mock_rabbitmq, upload_dir):
    """Test uploading a valid PDF file."""
    response = client.post(
        "/v1/upload",
        files={"file": ("test_document.pdf", valid_pdf_content, "application/pdf")},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "accepted"
    assert data["filename"] == "test_document.pdf"
    assert data["original_filename"] == "test_document.pdf"
    assert data["size"] == len(valid_pdf_content)
    assert "upload_id" in data
    assert "message" in data

    # Verify file was written
    uploaded_file = upload_dir / "test_document.pdf"
    assert uploaded_file.exists()
    assert uploaded_file.read_bytes() == valid_pdf_content

    # Verify RabbitMQ was called
    mock_rabbitmq.queue_declare.assert_called_once()
    mock_rabbitmq.basic_publish.assert_called_once()


def test_upload_invalid_content_type(client: TestClient, valid_pdf_content: bytes, upload_dir):
    """Test uploading with wrong content type."""
    response = client.post(
        "/v1/upload",
        files={"file": ("test.pdf", valid_pdf_content, "text/plain")},
    )

    assert response.status_code == 400
    assert "Invalid file type" in response.json()["detail"]


def test_upload_invalid_extension(client: TestClient, valid_pdf_content: bytes, upload_dir):
    """Test uploading with wrong file extension."""
    response = client.post(
        "/v1/upload",
        files={"file": ("test.txt", valid_pdf_content, "application/pdf")},
    )

    assert response.status_code == 400
    assert ".pdf extension" in response.json()["detail"]


def test_upload_invalid_pdf_content(client: TestClient, upload_dir):
    """Test uploading a file without PDF magic number."""
    fake_content = b"This is not a PDF file"

    response = client.post(
        "/v1/upload",
        files={"file": ("test.pdf", fake_content, "application/pdf")},
    )

    assert response.status_code == 400
    assert "PDF header" in response.json()["detail"]


def test_upload_file_too_large(client: TestClient, upload_dir):
    """Test uploading a file exceeding size limit."""
    from config import settings
    # Temporarily change the limit
    original_limit = settings.max_upload_size_mb
    object.__setattr__(settings, "max_upload_size_mb", 1)
    
    try:
        large_content = b"%PDF-1.4\n" + b"X" * (2 * 1024 * 1024)  # 2MB

        response = client.post(
            "/v1/upload",
            files={"file": ("large.pdf", large_content, "application/pdf")},
        )

        assert response.status_code == 413
        assert "exceeds" in response.json()["detail"]
    finally:
        object.__setattr__(settings, "max_upload_size_mb", original_limit)


def test_upload_filename_sanitization(
    client: TestClient, valid_pdf_content: bytes, mock_rabbitmq, upload_dir
):
    """Test that unsafe filenames are sanitized."""
    response = client.post(
        "/v1/upload",
        files={"file": ("../../../etc/passwd.pdf", valid_pdf_content, "application/pdf")},
    )

    assert response.status_code == 200
    data = response.json()

    # Verify filename is sanitized (no path traversal)
    assert data["filename"] == "passwd.pdf"
    assert not data["filename"].startswith("..")
    assert "/" not in data["filename"]
    assert "\\" not in data["filename"]


def test_upload_filename_collision(
    client: TestClient, valid_pdf_content: bytes, mock_rabbitmq, upload_dir
):
    """Test filename collision handling with timestamp."""
    # Create first file
    response1 = client.post(
        "/v1/upload",
        files={"file": ("document.pdf", valid_pdf_content, "application/pdf")},
    )
    assert response1.status_code == 200

    # Upload same filename again
    response2 = client.post(
        "/v1/upload",
        files={"file": ("document.pdf", valid_pdf_content, "application/pdf")},
    )
    assert response2.status_code == 200

    data1 = response1.json()
    data2 = response2.json()

    # Filenames should be different (second has timestamp)
    assert data1["filename"] == "document.pdf"
    assert data2["filename"].startswith("document_")
    assert data2["filename"].endswith(".pdf")
    assert data1["filename"] != data2["filename"]


def test_upload_rabbitmq_failure(client: TestClient, valid_pdf_content: bytes, upload_dir):
    """Test upload when RabbitMQ is unavailable."""
    with patch("main.pika.BlockingConnection") as mock_conn:
        import pika

        mock_conn.side_effect = pika.exceptions.AMQPConnectionError("Connection failed")

        response = client.post(
            "/v1/upload",
            files={"file": ("test.pdf", valid_pdf_content, "application/pdf")},
        )

        assert response.status_code == 502
        assert "Failed to enqueue" in response.json()["detail"]

        # Verify file was cleaned up after RabbitMQ failure
        assert not (upload_dir / "test.pdf").exists()


def test_upload_storage_failure(client: TestClient, valid_pdf_content: bytes):
    """Test upload when file write fails."""
    from config import settings
    
    mock_path = Mock()
    mock_path.mkdir = Mock()
    mock_path.__truediv__ = Mock(return_value=mock_path)
    mock_path.exists.return_value = False
    mock_path.write_bytes.side_effect = OSError("Disk full")
    
    original_dir = settings.upload_dir
    object.__setattr__(settings, "upload_dir", mock_path)
    
    try:
        response = client.post(
            "/v1/upload",
            files={"file": ("test.pdf", valid_pdf_content, "application/pdf")},
        )

        assert response.status_code == 500
        assert "Failed to save" in response.json()["detail"]
    finally:
        object.__setattr__(settings, "upload_dir", original_dir)


def test_upload_special_characters_in_filename(
    client: TestClient, valid_pdf_content: bytes, mock_rabbitmq, upload_dir
):
    """Test filename with special characters is sanitized."""
    response = client.post(
        "/v1/upload",
        files={"file": ("my<file>name?.pdf", valid_pdf_content, "application/pdf")},
    )

    assert response.status_code == 200
    data = response.json()

    # Special characters should be replaced with underscores
    assert "<" not in data["filename"]
    assert ">" not in data["filename"]
    assert "?" not in data["filename"]
    assert data["filename"].endswith(".pdf")
