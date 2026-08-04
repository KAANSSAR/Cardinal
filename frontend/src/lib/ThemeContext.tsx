import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type TerminalTheme = "amber" | "cyan" | "green";

const STORAGE_KEY = "cardinal-theme";
const DEFAULT_THEME: TerminalTheme = "amber";

interface ThemeContextValue {
  theme: TerminalTheme;
  setTheme: (theme: TerminalTheme) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

function readStoredTheme(): TerminalTheme {
  if (typeof window === "undefined") return DEFAULT_THEME;
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "amber" || stored === "cyan" || stored === "green") return stored;
  return DEFAULT_THEME;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<TerminalTheme>(readStoredTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    window.localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  function setTheme(next: TerminalTheme) {
    setThemeState(next);
  }

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return ctx;
}

export const THEME_DOTS: Record<TerminalTheme, string> = {
  amber: "#f5b942",
  cyan: "#22d3ee",
  green: "#39ff6a",
};

export const THEME_LABELS: Record<TerminalTheme, string> = {
  amber: "Amber",
  cyan: "Cyan",
  green: "Green",
};