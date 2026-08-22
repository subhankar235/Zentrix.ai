import { API_BASE_URL } from './client';

export interface SseSubscriptionOptions<T> {
  endpoint: string;
  onMessage: (data: T) => void;
  onError?: (error: Event) => void;
  onOpen?: () => void;
}

export function subscribeToSse<T>({
  endpoint,
  onMessage,
  onError,
  onOpen,
}: SseSubscriptionOptions<T>): () => void {
  const url = endpoint.startsWith('http')
    ? endpoint
    : `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

  if (typeof window === 'undefined' || typeof EventSource === 'undefined') {
    return () => {};
  }

  const eventSource = new EventSource(url, { withCredentials: true });

  eventSource.onopen = () => {
    onOpen?.();
  };

  eventSource.onmessage = (event) => {
    try {
      const parsed = JSON.parse(event.data) as T;
      onMessage(parsed);
    } catch {
      onMessage(event.data as unknown as T);
    }
  };

  eventSource.onerror = (err) => {
    onError?.(err);
  };

  return () => {
    eventSource.close();
  };
}
