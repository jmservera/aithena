import { useState, useCallback } from 'react';
import { applyAuthorizationHeader, buildApiUrl, notifyAuthFailure } from '../api';

const uploadUrl = buildApiUrl('/v1/upload');

export interface UploadProgress {
  loaded: number;
  total: number;
  percentage: number;
}

export interface UploadResult {
  filename: string;
  size: number;
  status: string;
  message: string;
}

export interface UploadState {
  uploading: boolean;
  progress: UploadProgress | null;
  result: UploadResult | null;
  error: string | null;
}

interface UseUploadReturn extends UploadState {
  uploadFile: (file: File) => Promise<void>;
  reset: () => void;
}

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

export function useUpload(): UseUploadReturn {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const uploadFile = useCallback(async (file: File) => {
    // Client-side validation
    if (!file.type || file.type !== 'application/pdf') {
      setError('Only PDF files are supported');
      return;
    }

    if (file.size > MAX_FILE_SIZE) {
      setError('File size exceeds 50MB limit');
      return;
    }

    // Reset state
    setUploading(true);
    setProgress(null);
    setResult(null);
    setError(null);

    return new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const formData = new FormData();
      formData.append('file', file);

      // Track upload progress
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          setProgress({
            loaded: e.loaded,
            total: e.total,
            percentage: Math.round((e.loaded / e.total) * 100),
          });
        }
      });

      // Handle completion
      xhr.addEventListener('load', () => {
        setUploading(false);

        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const data = JSON.parse(xhr.responseText);
            setResult(data);
            resolve();
          } catch {
            const msg = 'Invalid response from server';
            setError(msg);
            reject(new Error(msg));
          }
        } else {
          // Handle error responses
          let errorMessage = 'Upload failed';

          try {
            const errorData = JSON.parse(xhr.responseText);
            errorMessage = errorData.detail || errorData.message || errorMessage;
          } catch {
            // Use status-based message if JSON parsing fails
            if (xhr.status === 400) {
              errorMessage = 'Invalid file. Please ensure it is a valid PDF.';
            } else if (xhr.status === 401 || xhr.status === 403) {
              errorMessage = 'Your session has expired. Please sign in again.';
            } else if (xhr.status === 413) {
              errorMessage = 'File is too large. Maximum size is 50MB.';
            } else if (xhr.status === 429) {
              errorMessage = 'Upload rate limit exceeded. Please try again in a minute.';
            } else if (xhr.status === 500) {
              errorMessage = 'Server error. Please try again later.';
            } else if (xhr.status === 502) {
              errorMessage = 'Service temporarily unavailable. Please try again.';
            }
          }

          if (xhr.status === 401 || xhr.status === 403) {
            notifyAuthFailure();
          }

          setError(errorMessage);
          reject(new Error(errorMessage));
        }
      });

      // Handle network errors
      xhr.addEventListener('error', () => {
        setUploading(false);
        const msg = 'Network error. Please check your connection.';
        setError(msg);
        reject(new Error(msg));
      });

      // Handle abort
      xhr.addEventListener('abort', () => {
        setUploading(false);
        const msg = 'Upload cancelled';
        setError(msg);
        reject(new Error(msg));
      });

      xhr.open('POST', uploadUrl);
      applyAuthorizationHeader(xhr);
      xhr.send(formData);
    });
  }, []);

  const reset = useCallback(() => {
    setUploading(false);
    setProgress(null);
    setResult(null);
    setError(null);
  }, []);

  return {
    uploading,
    progress,
    result,
    error,
    uploadFile,
    reset,
  };
}
