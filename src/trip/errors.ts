import { isApiError, type ApiErrorCode } from '../api'

export const BUILD_UNAVAILABLE = "Plan building isn't available yet. Places and the map still work."
export const PLAN_CHANGED = 'The plan changed. Review it and accept again.'
export const PLACE_NOT_FOUND = "Couldn't find that place"

/** A user-facing sentence for a failed request. `overrides` maps backend error codes to copy. */
export function errorMessage(error: unknown, overrides: Partial<Record<ApiErrorCode, string>> = {}): string {
  if (isApiError(error)) {
    const custom = overrides[error.code]
    if (custom) return custom
    if (error.code === 'network_error') return "Couldn't reach Questline. Check your connection and try again."
    return error.message
  }
  return error instanceof Error ? error.message : 'Something went wrong. Try again.'
}

export function errorCode(error: unknown): ApiErrorCode | null {
  return isApiError(error) ? error.code : null
}

/** Network failures and 5xx may not have reached the backend, so the same request is worth retrying. */
export function isRetryable(error: unknown): boolean {
  return !isApiError(error) || error.status === 0 || error.status >= 500
}

export function isConflict(error: unknown): boolean {
  return isApiError(error) && error.status === 409
}
