export function humanizeApiError(err: unknown, status?: number): string {
  const code = status ?? (err as { status?: number }).status
  if (code === 401) return 'Your session has expired. Please log in again.'
  if (code === 403) return 'You do not have permission to do this.'
  if (code === 404) return 'The requested item was not found.'
  if (code === 500) return 'Something went wrong. Please try again.'
  if (err instanceof Error && err.message && err.message !== 'Unauthorized') {
    return err.message
  }
  return 'Something went wrong. Please try again.'
}
