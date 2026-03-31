const DEV_UI_PORTS = new Set(['3000', '4173', '4174', '5173', '5174']);
const authFailureHandlers = new Set<() => void>();

export const AUTH_TOKEN_STORAGE_KEY = 'aithena.auth.token';

export interface AuthUser {
  id: number | string;
  username: string;
  role: string;
}

export interface AuthSession {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
}

interface ApiFetchOptions extends RequestInit {
  skipAuth?: boolean;
  skipUnauthorizedHandler?: boolean;
}

function normalizeApiBaseUrl(rawUrl?: string): string {
  const trimmed = rawUrl?.trim();
  if (!trimmed || trimmed === '.') {
    if (typeof window !== 'undefined') {
      const { hostname, port, protocol } = window.location;
      const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1';

      if (isLocalhost && DEV_UI_PORTS.has(port)) {
        return `${protocol}//${hostname}:8080`;
      }
    }

    return '';
  }

  return trimmed.replace(/\/+$/, '');
}

function withAuthorization(headers?: HeadersInit, skipAuth = false): Headers {
  const nextHeaders = new Headers(headers ?? {});
  const authHeader = !skipAuth ? getAuthorizationHeaderValue() : null;

  if (authHeader && !nextHeaders.has('Authorization')) {
    nextHeaders.set('Authorization', authHeader);
  }

  return nextHeaders;
}

function createRequestUrl(input: string): string {
  return /^https?:\/\//i.test(input) ? input : buildApiUrl(input);
}

const apiBaseUrl = normalizeApiBaseUrl(import.meta.env.VITE_API_URL);

export function buildApiUrl(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${apiBaseUrl}${normalizedPath}`;
}

export function resolveDocumentUrl(documentUrl?: string | null): string | null {
  if (!documentUrl) {
    return null;
  }

  if (/^https?:\/\//i.test(documentUrl)) {
    // Backend-generated /documents/ URLs may use an internal hostname or
    // wrong scheme (http behind a reverse proxy).  Normalise them to a
    // relative path so the browser routes through the same origin.
    try {
      const parsed = new URL(documentUrl);
      if (parsed.pathname.startsWith('/documents/')) {
        return buildApiUrl(parsed.pathname);
      }
      // When DOCUMENT_URL_BASE points to the same origin without the
      // /documents/ prefix the resulting URL lands on the catch-all nginx
      // location which sends X-Frame-Options: DENY, breaking the embedded
      // PDF viewer.  Re-route same-origin URLs through /documents/{token}.
      if (typeof window !== 'undefined' && parsed.origin === window.location.origin) {
        const lastSegment = parsed.pathname.split('/').filter(Boolean).pop();
        if (lastSegment) {
          return buildApiUrl(`/documents/${lastSegment}`);
        }
      }
    } catch {
      // Malformed URL — fall through and return as-is
    }
    return documentUrl;
  }

  return buildApiUrl(documentUrl);
}

export function getStoredToken(): string | null {
  if (typeof window === 'undefined') {
    return null;
  }

  return (
    window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) ??
    window.sessionStorage.getItem(AUTH_TOKEN_STORAGE_KEY)
  );
}

export function storeToken(token: string, persistent = true): void {
  if (typeof window !== 'undefined') {
    if (persistent) {
      window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
    } else {
      window.sessionStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
    }
  }
}

export function clearStoredToken(): void {
  if (typeof window !== 'undefined') {
    window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
    window.sessionStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
  }
}

export function getAuthorizationHeaderValue(): string | null {
  const token = getStoredToken();
  return token ? `Bearer ${token}` : null;
}

export function registerAuthFailureHandler(handler: () => void): () => void {
  authFailureHandlers.add(handler);
  return () => {
    authFailureHandlers.delete(handler);
  };
}

export function notifyAuthFailure(): void {
  clearStoredToken();
  authFailureHandlers.forEach((handler) => handler());
}

export async function apiFetch(input: string, options: ApiFetchOptions = {}): Promise<Response> {
  const { skipAuth = false, skipUnauthorizedHandler = false, headers, ...rest } = options;
  const response = await fetch(createRequestUrl(input), {
    ...rest,
    credentials: 'include',
    headers: withAuthorization(headers, skipAuth),
  });

  if ((response.status === 401 || response.status === 403) && !skipUnauthorizedHandler) {
    notifyAuthFailure();
  }

  return response;
}

export function applyAuthorizationHeader(xhr: XMLHttpRequest): void {
  const authHeader = getAuthorizationHeaderValue();
  if (authHeader) {
    xhr.setRequestHeader('Authorization', authHeader);
  }
}
