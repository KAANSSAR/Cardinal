import { Outlet } from "react-router-dom";
import Header from "./Header";
import TickerTape from "./TickerTape";

export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col bg-term-bg">
      <Header />
      <TickerTape />

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t border-term-border-faint py-6">
        <div className="mx-auto max-w-7xl px-6 text-center font-mono text-[11px] text-term-text-faint tracking-wide">
          CARDINAL — FUNDAMENTAL, QUANT, AND ALGO ANALYSIS IN ONE TERMINAL.
        </div>
      </footer>
    </div>
  );
}