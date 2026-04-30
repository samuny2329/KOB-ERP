/** Users + companies API surface. */
import { api, type CompanyRead, type UserRead } from "@/lib/api";

export interface UserCreatePayload {
  email: string;
  password: string;
  full_name: string;
  is_superuser?: boolean;
  default_company_id?: number | null;
  company_ids?: number[];
}

export const usersApi = {
  list: () => api.get<UserRead[]>("/users").then((r) => r.data),
  create: (body: UserCreatePayload) =>
    api.post<UserRead>("/users", body).then((r) => r.data),
};

export const companiesApi = {
  list: () => api.get<CompanyRead[]>("/companies").then((r) => r.data),
  switch: (id: number) =>
    api.post<UserRead>(`/companies/${id}/switch`).then((r) => r.data),
};
