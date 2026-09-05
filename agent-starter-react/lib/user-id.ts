/**
 * Stable anonymous user ID for memory/continuity.
 *
 * Generated once per browser and kept in localStorage, so the voice agent
 * remembers a returning user across sessions without any signup. If storage
 * is unavailable (private windows, blocked storage), returns undefined and
 * the server falls back to a random identity - the app still works, the
 * agent just won't remember that visitor next time.
 */
const STORAGE_KEY = 'career-agent-user-id';

export function getStableUserId(): string | undefined {
  if (typeof window === 'undefined') return undefined;
  try {
    let id = window.localStorage.getItem(STORAGE_KEY);
    if (!id || !/^user_[A-Za-z0-9-]{8,64}$/.test(id)) {
      id = `user_${crypto.randomUUID()}`;
      window.localStorage.setItem(STORAGE_KEY, id);
    }
    return id;
  } catch {
    return undefined;
  }
}
