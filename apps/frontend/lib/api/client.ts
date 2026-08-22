/**
 * Universal HTTP Client for Zentrix.ai Frontend.
 * Uses NEXT_PUBLIC_API_URL environment variable and attaches Clerk session tokens.
 */

const configuredApiUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const API_BASE_URL = configuredApiUrl.replace(/\/$/, '').endsWith('/api/v1')
  ? configuredApiUrl.replace(/\/$/, '')
  : `${configuredApiUrl.replace(/\/$/, '')}/api/v1`;

export interface ApiErrorResponse {
  detail?: string | { message?: string; msg?: string }[] | Record<string, unknown>;
  message?: string;
  status?: number;
}

export class ApiError extends Error {
  status: number;
  data?: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined | null>;
}

export type AuthTokenGetter = () => Promise<string | null> | string | null;

let globalAuthTokenGetter: AuthTokenGetter | null = null;

export function setApiAuthTokenGetter(getter: AuthTokenGetter | null) {
  globalAuthTokenGetter = getter;
}

export async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { params, headers, ...customConfig } = options;

  let url = endpoint.startsWith('http')
    ? endpoint
    : `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, String(value));
      }
    });
    const queryString = searchParams.toString();
    if (queryString) {
      url += (url.includes('?') ? '&' : '?') + queryString;
    }
  }

  const defaultHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  // Retrieve token dynamically from Clerk Auth bridge or fallback
  let token: string | null = null;

  if (globalAuthTokenGetter) {
    try {
      token = await globalAuthTokenGetter();
    } catch (err) {
      console.warn('[apiClient] Error retrieving session token from auth getter:', err);
    }
  }

  if (!token && typeof window !== 'undefined') {
    const clerk = (window as unknown as { Clerk?: { session?: { getToken: () => Promise<string | null> } } }).Clerk;
    if (clerk?.session) {
      try {
        token = await clerk.session.getToken();
      } catch {
        // Continue to fallback
      }
    }
    if (!token) {
      token = localStorage.getItem('zentrix_auth_token');
    }
  }

  if (token) {
    defaultHeaders['Authorization'] = `Bearer ${token}`;
  }

  const config: RequestInit = {
    method: 'GET',
    credentials: 'include',
    headers: {
      ...defaultHeaders,
      ...headers,
    },
    ...customConfig,
  };

  try {
    const response = await fetch(url, config);

    if (!response.ok) {
      let errorData: ApiErrorResponse | null = null;
      try {
        errorData = await response.json();
      } catch {
        // Not JSON
      }

      let message = `API error ${response.status}: ${response.statusText}`;
      if (errorData?.detail) {
        if (typeof errorData.detail === 'string') {
          message = errorData.detail;
        } else if (Array.isArray(errorData.detail)) {
          message = errorData.detail
            .map((e: unknown) => {
              if (typeof e === 'object' && e !== null) {
                const item = e as Record<string, unknown>;
                return String(item.msg || item.message || JSON.stringify(e));
              }
              return String(e);
            })
            .join(', ');
        }
      } else if (errorData?.message) {
        message = errorData.message;
      }

      throw new ApiError(message, response.status, errorData);
    }

    if (response.status === 204) {
      return {} as T;
    }

    return (await response.json()) as T;
  } catch (err: unknown) {
    if (err instanceof ApiError) {
      throw err;
    }
    const message = err instanceof Error ? err.message : 'Network error';
    throw new ApiError(message, 0, err);
  }
}

export const apiClient = {
  get: <T>(endpoint: string, options?: RequestOptions) =>
    request<T>(endpoint, { method: 'GET', ...options }),

  post: <T>(endpoint: string, body?: unknown, options?: RequestOptions) =>
    request<T>(endpoint, {
      method: 'POST',
      body: body !== undefined ? JSON.stringify(body) : undefined,
      ...options,
    }),

  put: <T>(endpoint: string, body?: unknown, options?: RequestOptions) =>
    request<T>(endpoint, {
      method: 'PUT',
      body: body !== undefined ? JSON.stringify(body) : undefined,
      ...options,
    }),

  patch: <T>(endpoint: string, body?: unknown, options?: RequestOptions) =>
    request<T>(endpoint, {
      method: 'PATCH',
      body: body !== undefined ? JSON.stringify(body) : undefined,
      ...options,
    }),

  delete: <T>(endpoint: string, options?: RequestOptions) =>
    request<T>(endpoint, { method: 'DELETE', ...options }),
};
