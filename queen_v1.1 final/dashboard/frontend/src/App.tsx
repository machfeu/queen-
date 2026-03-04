import { BrowserRouter, Routes, Route } from "react-router-dom";
import Shell from "./layout/Shell";
import Overview from "./pages/Overview";
import Goals from "./pages/Goals";
import Runs from "./pages/Runs";
import RunDetail from "./pages/RunDetail";
import Patches from "./pages/Patches";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Shell />}>
          <Route index element={<Overview />} />
          <Route path="/goals" element={<Goals />} />
          <Route path="/runs" element={<Runs />} />
          <Route path="/runs/:runId" element={<RunDetail />} />
          <Route path="/patches" element={<Patches />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

function NotFound() {
  return (
    <div style={{ padding: 40, textAlign: "center" }}>
      <h2 style={{ fontSize: 48, marginBottom: 8 }}>404</h2>
      <p style={{ color: "var(--mantine-color-dimmed)" }}>Page introuvable.</p>
    </div>
  );
}
