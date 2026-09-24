const USER_ID_KEY = "shmeter_user_id";
const THEME_KEY = "shmeter_theme";

export type Theme = "dark" | "light";

export function newId(): string {
  return crypto.randomUUID?.() ?? String(Date.now()) + Math.random().toString(16).slice(2);
}

export function getOrCreateUserId(): string {
  let id: string | null = null;
  try {
    id = localStorage.getItem(USER_ID_KEY);
  } catch {
    // localStorage unavailable -- use an in-memory id for this page load
  }
  if (!id) {
    id = newId();
    try {
      localStorage.setItem(USER_ID_KEY, id);
    } catch {
      // ignore
    }
  }
  return id;
}

export function loadTheme(): Theme | null {
  try {
    const t = localStorage.getItem(THEME_KEY);
    return t === "dark" || t === "light" ? t : null;
  } catch {
    return null;
  }
}

export function saveTheme(theme: Theme): void {
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    // ignore
  }
}
