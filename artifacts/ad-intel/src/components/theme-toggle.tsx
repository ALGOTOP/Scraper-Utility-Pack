import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/hooks/use-theme";
import { cn } from "@/lib/utils";

export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const isDark = theme === "dark";

  return (
    <button
      onClick={toggle}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      className={cn(
        "relative flex items-center h-6 w-11 rounded-full transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        isDark ? "bg-sidebar-primary/20" : "bg-sidebar-accent"
      )}
    >
      {/* Track icons */}
      <Sun className="absolute left-1 h-3 w-3 text-sidebar-foreground/50 transition-opacity duration-200"
        style={{ opacity: isDark ? 0.4 : 1 }}
      />
      <Moon className="absolute right-1 h-3 w-3 text-sidebar-foreground/50 transition-opacity duration-200"
        style={{ opacity: isDark ? 1 : 0.4 }}
      />
      {/* Thumb */}
      <span
        className={cn(
          "absolute h-4 w-4 rounded-full bg-sidebar-foreground shadow-sm transition-transform duration-200",
          isDark ? "translate-x-[22px]" : "translate-x-[2px]"
        )}
      />
    </button>
  );
}
