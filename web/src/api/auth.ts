import { apiFetch } from "./client";
import type { AuthResponse, User } from "@/types";

export async function register(data: {
  email: string;
  password: string;
  name: string;
}): Promise<AuthResponse> {
  return apiFetch<AuthResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function login(data: {
  email: string;
  password: string;
}): Promise<AuthResponse> {
  return apiFetch<AuthResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getMe(): Promise<User> {
  return apiFetch<User>("/auth/me");
}

export async function updateProfile(data: {
  name?: string;
  current_password?: string;
  new_password?: string;
}): Promise<User> {
  return apiFetch<User>("/auth/me", {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}
