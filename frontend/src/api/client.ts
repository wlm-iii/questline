// Empty means same origin; in development Vite proxies /api to the backend (see vite.config.ts).
const apiOrigin: string = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '')
const apiPrefix = '/api/v1'

/** Error codes the backend sends in `{ error: { code, message } }`, plus client-side ones. */
export type ApiErrorCode =
  | 'unauthorized'
  | 'forbidden'
  | 'not_found'
  | 'conflict'
  | 'import_too_large'
  | 'validation_error'
  | 'provider_unavailable'
  | 'cross_trip_reference'
  | 'service_only'
  | 'place_not_found'
  | 'plan_in_progress'
  | 'request_failed'
  | 'network_error'
  | (string & {})

export class ApiError extends Error {
  readonly status: number
  readonly code: ApiErrorCode
  /** Extra fields from the error body, such as `generation_id` on `plan_in_progress`. */
  readonly details: Record<string, unknown>

  constructor(status: number, code: ApiErrorCode, message: string, details: Record<string, unknown> = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError
}

/** True when the request was cancelled through its AbortSignal. */
export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

export type RequestOptions = {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
  memberToken?: string
  headers?: Record<string, string>
  signal?: AbortSignal
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json', ...options.headers }
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'
  if (options.memberToken) headers['X-Member-Token'] = options.memberToken

  let response: Response
  try {
    response = await fetch(`${apiOrigin}${apiPrefix}${path}`, {
      method: options.method ?? 'GET',
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
    })
  } catch (error) {
    if (isAbortError(error)) throw error
    throw new ApiError(0, 'network_error', "Couldn't reach the Questline API")
  }

  if (response.status === 204) return undefined as T
  const payload: unknown = await response.json().catch(() => undefined)
  if (response.ok) return payload as T
  throw errorFromResponse(response.status, payload)
}

function errorFromResponse(status: number, payload: unknown): ApiError {
  const error = isRecord(payload) && isRecord(payload.error) ? payload.error : {}
  const { code, message, ...details } = error
  return new ApiError(
    status,
    typeof code === 'string' ? code : 'request_failed',
    typeof message === 'string' ? message : `Request failed with status ${status}`,
    details,
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
