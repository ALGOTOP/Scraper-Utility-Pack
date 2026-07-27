import { Link, useLocation } from "wouter";
import { Database, Search, CheckSquare, Bookmark, Target } from "lucide-react";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "@/components/theme-toggle";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: Target },
  { href: "/jobs", label: "Scrape Jobs", icon: Database },
  { href: "/leads", label: "All Leads", icon: Search },
  { href: "/review", label: "Needs Review", icon: CheckSquare },
  { href: "/saved-searches", label: "Saved Searches", icon: Bookmark },
];

export function Layout({ children }: { children: React.ReactNode }) {
  const [location] = useLocation();

  return (
    <div className="flex h-[100dvh] w-full overflow-hidden bg-background">
      <aside className="w-64 flex-shrink-0 border-r bg-sidebar flex flex-col">
        <div className="p-6 flex items-center gap-2">
          <div className="h-6 w-6 bg-primary text-primary-foreground flex items-center justify-center rounded-sm font-bold text-sm">
            A
          </div>
          <span className="font-semibold text-lg tracking-tight text-sidebar-foreground flex-1">Ad Intel</span>
          <ThemeToggle />
        </div>
        <nav className="flex-1 px-4 py-2 space-y-1">
          {NAV_ITEMS.map((item) => {
            const isActive = location === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-md transition-colors",
                  isActive
                    ? "bg-sidebar-primary text-sidebar-primary-foreground shadow-sm"
                    : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                )}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>
      <main className="flex-1 overflow-auto flex flex-col min-w-0">
        <div className="flex-1 p-8 max-w-7xl mx-auto w-full">
          {children}
        </div>
      </main>
    </div>
  );
}
