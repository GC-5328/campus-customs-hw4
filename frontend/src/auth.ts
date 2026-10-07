// Account API calls. The session lives in an HttpOnly cookie set by the
// backend, so nothing secret is stored in JavaScript.

export interface User {
  id: number
  first_name: string | null
  last_name: string | null
  name: string
  email: string
}

export interface SignupData {
  first_name: string
  last_name: string
  email: string
  password: string
  confirm_password: string
}

async function postJson<T>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => null)
    const detail = typeof data?.detail === 'string' ? data.detail : 'Something went wrong. Please try again.'
    throw new Error(detail)
  }
  return (res.status === 204 ? null : await res.json()) as T
}

export function signup(data: SignupData): Promise<User> {
  return postJson<User>('/api/auth/signup', data)
}

export function login(email: string, password: string): Promise<User> {
  return postJson<User>('/api/auth/login', { email, password })
}

export function logout(): Promise<null> {
  return postJson<null>('/api/auth/logout')
}

export async function fetchCurrentUser(): Promise<User | null> {
  const res = await fetch('/api/auth/me')
  return res.ok ? ((await res.json()) as User) : null
}
