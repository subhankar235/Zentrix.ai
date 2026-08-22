import { apiClient } from './client';
import type { UserProfile } from '../../stores/use-auth-store';

export interface LoginPayload {
  email: string;
  password?: string;
}

export interface AuthResponse {
  user: UserProfile;
  token: string;
}

export const authApi = {
  login: async (payload: LoginPayload): Promise<AuthResponse> => {
    return apiClient.post<AuthResponse>('/auth/login', payload);
  },

  register: async (payload: LoginPayload & { fullName: string }): Promise<AuthResponse> => {
    return apiClient.post<AuthResponse>('/auth/register', payload);
  },

  getMe: async (): Promise<UserProfile> => {
    return apiClient.get<UserProfile>('/auth/me');
  },

  logout: async (): Promise<void> => {
    try {
      await apiClient.post('/auth/logout');
    } finally {
      if (typeof window !== 'undefined') {
        localStorage.removeItem('zentrix_auth_token');
      }
    }
  },
};
