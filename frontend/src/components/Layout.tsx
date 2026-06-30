import { Link, Outlet } from "react-router-dom";

export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col bg-offwhite">
      <header className="border-b border-slate-200 bg-navy">
        <div className="mx-auto max-w-6xl px-6 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-baseline gap-2">
            <span className="font-display text-2xl font-bold text-white tracking-tight">
              Cardinal
            </span>
            <span className="hidden sm:inline text-xs text-teal-light font-sans">
              equity analysis terminal
            </span>
          </Link>
          <nav className="flex items-center gap-1 text-sm font-sans">
            {[
              { label: "Fundamental", color: "bg-teal/20 text-teal-light" },
              { label: "Quant", color: "bg-blue/20 text-blue-light" },
              { label: "Backtest", color: "bg-purple/20 text-purple-light" },
              { label: "AI", color: "bg-amber/20 text-amber" },
            ].map((lens) => (
              <span
                key={lens.label}
                className={`hidden md:inline-block px-3 py-1 rounded-full text-xs font-medium ${lens.color}`}
              >
                {lens.label}
              </span>
            ))}
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t border-slate-200 py-6">
        <div className="mx-auto max-w-6xl px-6 text-xs text-slate text-center">
          Cardinal — fundamental, quant, and algo analysis in one terminal.
        </div>
      </footer>
    </div>
  );
}
