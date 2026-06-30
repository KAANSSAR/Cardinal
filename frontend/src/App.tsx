import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Home from "./pages/Home";
import TickerPage from "./pages/TickerPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Home />} />
          <Route path="/ticker/:symbol" element={<TickerPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
