/** Display preferences are optional; unavailable storage must not block the UI. */
export function readDisplayPreference(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

export function writeDisplayPreference(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    // Keep the current display setting for this session when persistence is unavailable.
  }
}
