import { BrowserRouter, Route, Routes } from "react-router-dom";
import PlantDetail from "./pages/PlantDetail";
import PlantList from "./pages/PlantList";

export default function App() {
  return (
    <BrowserRouter>
      <div style={{ maxWidth: 960, margin: "0 auto", padding: "24px 16px" }}>
        <header
          style={{
            borderBottom: "2px solid #e0e0e0",
            paddingBottom: 12,
            marginBottom: 24,
          }}
        >
          <h1
            style={{
              margin: 0,
              fontSize: 20,
              fontWeight: 700,
              letterSpacing: -0.5,
              color: "#2e7d32",
            }}
          >
            Plant Tracker
          </h1>
          <p style={{ margin: "4px 0 0", fontSize: 13, color: "#888" }}>
            Marchantia polymorpha growth &amp; health monitor
          </p>
        </header>

        <Routes>
          <Route path="/" element={<PlantList />} />
          <Route path="/plants/:id" element={<PlantDetail />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
