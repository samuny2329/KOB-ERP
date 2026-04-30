/** Axios client with bearer token + automatic refresh on 401. */
import axios, { type AxiosError, type AxiosRequestConfig } from "axios";

const API_BASE = "/api/v1";

export const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

const ACCESS_KEY = "kob.access";
const REFRESH_KEY = "kob.refresh";

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}
export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}
export function setTokens(access: string, refresh: string): void {
  localStorage.setItem(ACCESS_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}
export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let refreshing: Promise<string> | null = null;

async function refreshAccess(): Promise<string> {
  const rt = getRefreshToken();
  if (!rt) throw new Error("no refresh token");
  const resp = await axios.post(`${API_BASE}/auth/refresh`, { refresh_token: rt });
  setTokens(resp.data.access_token, resp.data.refresh_token);
  return resp.data.access_token;
}

api.interceptors.response.use(
  (resp) => resp,
  async (error: AxiosError) => {
    const original = error.config as AxiosRequestConfig & { _retry?: boolean };
    if (error.response?.status === 401 && !original._retry && getRefreshToken()) {
      original._retry = true;
      try {
        refreshing ??= refreshAccess().finally(() => {
          refreshing = null;
        });
        const fresh = await refreshing;
        if (original.headers) {
          original.headers.Authorization = `Bearer ${fresh}`;
        }
        return api.request(original);
      } catch {
        clearTokens();
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  },
);

export interface CompanyRead {
  id: number;
  code: string;
  name: string;
  legal_name: string | null;
  tax_id: string | null;
  address: string | null;
  phone: string | null;
  email: string | null;
  currency: string;
  locale: string;
  timezone: string;
  parent_id: number | null;
  is_active: boolean;
}

export interface UserRead {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
  last_login_at: string | null;
  created_at: string;
  default_company_id: number | null;
  preferred_locale: string;
  companies: CompanyRead[];
  default_company: CompanyRead | null;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export async function login(email: string, password: string): Promise<TokenPair> {
  const resp = await api.post<TokenPair>("/auth/login", { email, password });
  return resp.data;
}

export async function fetchMe(): Promise<UserRead> {
  const resp = await api.get<UserRead>("/auth/me");
  return resp.data;
}
