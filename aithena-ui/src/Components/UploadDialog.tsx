import { useState, useCallback, DragEvent, ChangeEvent } from "react";
import "./UploadDialog.css";

const uploadUrl = `${import.meta.env.VITE_API_URL}/v1/upload/`;

const MAX_FILE_SIZE_MB = 100;
const MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024;

type UploadState = "idle" | "uploading" | "success" | "error";

interface UploadResult {
  filename: string;
  message: string;
  status: string;
}

interface UploadDialogProps {
  onClose: () => void;
  onSearchBook: (query: string) => void;
}

function validateFile(f: File): string {
  if (f.type !== "application/pdf" && !f.name.toLowerCase().endsWith(".pdf")) {
    return "Only PDF files are supported.";
  }
  if (f.size > MAX_FILE_SIZE) {
    return `File is too large. Maximum size is ${MAX_FILE_SIZE_MB} MB.`;
  }
  return "";
}

export default function UploadDialog({
  onClose,
  onSearchBook,
}: UploadDialogProps) {
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploadState, setUploadState] = useState<UploadState>("idle");
  const [error, setError] = useState<string>("");
  const [result, setResult] = useState<UploadResult | null>(null);

  const handleFile = useCallback((f: File) => {
    const err = validateFile(f);
    if (err) {
      setError(err);
      setFile(null);
    } else {
      setError("");
      setFile(f);
    }
  }, []);

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = () => setDragOver(false);

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) handleFile(dropped);
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) handleFile(selected);
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploadState("uploading");
    setError("");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(uploadUrl, {
        method: "POST",
        body: formData,
      });

      if (response.ok) {
        const data = (await response.json()) as UploadResult;
        setResult(data);
        setUploadState("success");
      } else {
        let errorMessage = `Upload failed (${response.status})`;
        try {
          const errData = (await response.json()) as {
            detail?: string | unknown;
          };
          if (errData.detail) {
            errorMessage =
              typeof errData.detail === "string"
                ? errData.detail
                : JSON.stringify(errData.detail);
          }
        } catch {
          // keep default message
        }
        setError(errorMessage);
        setUploadState("error");
      }
    } catch (err) {
      console.error("Upload network error:", err);
      setError("Network error. Please check your connection and try again.");
      setUploadState("error");
    }
  };

  const handleSearchBook = () => {
    if (result) {
      const query = result.filename
        .replace(/\.pdf$/i, "")
        .replace(/[_.()[\]{}]+/g, " ")
        .replace(/\s+/g, " ")
        .trim();
      onSearchBook(query);
    }
    onClose();
  };

  const handleRemoveFile = () => {
    setFile(null);
    setError("");
  };

  const handleOverlayClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) onClose();
  };

  return (
    <div className="upload-overlay" onClick={handleOverlayClick}>
      <div className="upload-dialog" role="dialog" aria-modal="true" aria-labelledby="upload-dialog-title">
        <div className="upload-dialog-header">
          <h2 id="upload-dialog-title">Upload PDF</h2>
          <button
            className="upload-close-btn"
            onClick={onClose}
            aria-label="Close upload dialog"
          >
            ✕
          </button>
        </div>

        {uploadState === "success" ? (
          <div className="upload-success">
            <div className="upload-success-icon" aria-hidden="true">✅</div>
            <p className="upload-success-title">Upload successful!</p>
            <p className="upload-success-message">
              {result?.message ||
                "Your PDF has been uploaded and will be indexed shortly."}
            </p>
            {result?.filename && (
              <p className="upload-success-filename">{result.filename}</p>
            )}
            <div className="upload-actions">
              <button className="upload-btn-primary" onClick={handleSearchBook}>
                🔍 Search for this book
              </button>
              <button className="upload-btn-secondary" onClick={onClose}>
                Close
              </button>
            </div>
          </div>
        ) : (
          <>
            <div
              className={`upload-dropzone${dragOver ? " drag-over" : ""}${file ? " has-file" : ""}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              {file ? (
                <div className="upload-file-info">
                  <span className="upload-file-icon" aria-hidden="true">📄</span>
                  <span className="upload-file-name" title={file.name}>
                    {file.name}
                  </span>
                  <span className="upload-file-size">
                    {(file.size / (1024 * 1024)).toFixed(1)} MB
                  </span>
                  <button
                    className="upload-remove-btn"
                    onClick={handleRemoveFile}
                    aria-label="Remove selected file"
                  >
                    ✕
                  </button>
                </div>
              ) : (
                <>
                  <span className="upload-drop-icon" aria-hidden="true">📂</span>
                  <p className="upload-drop-text">
                    Drag &amp; drop a PDF here, or
                  </p>
                  <label className="upload-btn-primary">
                    Browse files
                    <input
                      type="file"
                      accept=".pdf,application/pdf"
                      onChange={handleFileChange}
                      className="upload-file-input"
                      aria-label="Select PDF file"
                    />
                  </label>
                  <p className="upload-drop-hint">
                    PDF only · Maximum {MAX_FILE_SIZE_MB} MB
                  </p>
                </>
              )}
            </div>

            {error && (
              <div className="upload-error" role="alert">
                ⚠️ {error}
              </div>
            )}

            <div className="upload-actions">
              <button
                className="upload-btn-primary"
                onClick={handleUpload}
                disabled={!file || uploadState === "uploading"}
              >
                {uploadState === "uploading" ? (
                  <>
                    <span className="upload-spinner" aria-hidden="true" />
                    Uploading…
                  </>
                ) : (
                  "Upload"
                )}
              </button>
              <button
                className="upload-btn-secondary"
                onClick={onClose}
                disabled={uploadState === "uploading"}
              >
                Cancel
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
