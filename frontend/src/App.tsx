import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Home from "./pages/Home";
import TickerPage from "./pages/TickerPage";
import AdminDashboard from "./pages/AdminDashboard";
import { ThemeProvider } from "./lib/ThemeContext";

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          {/* Admin — no Layout wrapper (has its own header), still theme-aware */}
          <Route path="/admin" element={<AdminDashboard />} />
          {/* Main app */}
          <Route element={<Layout />}>
            <Route path="/" element={<Home />} />
            <Route path="/ticker/:symbol" element={<TickerPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}