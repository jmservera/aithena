const DEV_UI_PORTS = new Set(["3000", "4173", "4174", "5173", "5174"]);

function normalizeApiBaseUrl(rawUrl?: string): string {
  const trimmed = rawUrl?.trim();
  if (!trimmed || trimmed === ".") {
    if (typeof window !== "undefined") {
      const { hostname, port, protocol } = window.location;
      const isLocalhost = hostname === "localhost" || hostname === "127.0.0.1";

      if (isLocalhost && DEV_UI_PORTS.has(port)) {
        return `${protocol}//${hostname}:8080`;
      }
    }

    return "";
  }

  return trimmed.replace(/\/+$/, "");
}

const apiBaseUrl = normalizeApiBaseUrl(import.meta.env.VITE_API_URL);

export function buildApiUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${apiBaseUrl}${normalizedPath}`;
}

export function resolveDocumentUrl(documentUrl?: string | null): string | null {
  if (!documentUrl) {
    return null;
  }

  if (/^https?:\/\//i.test(documentUrl)) {
    return documentUrl;
  }

  return buildApiUrl(documentUrl);
}
