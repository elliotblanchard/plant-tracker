import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchPlants, triggerAnalysis, type PlantSummary } from "../api/client";
import AlertBanner from "../components/AlertBanner";

export default function PlantList() {
  const [plants, setPlants] = useState<PlantSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisMsg, setAnalysisMsg] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setPlants(await fetchPlants());
    } catch (err: any) {
      setError(err.message ?? "Failed to load plants");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleAnalyze = async () => {
    setAnalyzing(true);
    setAnalysisMsg(null);
    try {
      const result = await triggerAnalysis();
      setAnalysisMsg(
        `Processed ${result.images_processed} images, found ${result.plants_found} plant(s).` +
          (result.errors.length > 0
            ? ` ${result.errors.length} error(s).`
            : "")
      );
      await load();
    } catch (err: any) {
      setAnalysisMsg(`Analysis failed: ${err.message}`);
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 20,
        }}
      >
        <h1 style={{ margin: 0, fontSize: 24 }}>Plants</h1>
        <button
          onClick={handleAnalyze}
          disabled={analyzing}
          style={{
            padding: "8px 20px",
            background: analyzing ? "#bdbdbd" : "#4caf50",
            color: "#fff",
            border: "none",
            borderRadius: 6,
            cursor: analyzing ? "not-allowed" : "pointer",
            fontSize: 14,
            fontWeight: 500,
          }}
        >
          {analyzing ? "Analyzing..." : "Run Analysis"}
        </button>
      </div>

      {analysisMsg && <AlertBanner type="info" message={analysisMsg} />}
      {error && <AlertBanner type="danger" message={error} />}

      {loading ? (
        <p>Loading...</p>
      ) : plants.length === 0 ? (
        <p style={{ color: "#888" }}>
          No plants found. Place images in <code>test-plant/</code> and click
          &ldquo;Run Analysis&rdquo;.
        </p>
      ) : (
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            fontSize: 14,
          }}
        >
          <thead>
            <tr
              style={{
                borderBottom: "2px solid #e0e0e0",
                textAlign: "left",
              }}
            >
              <th style={thStyle}>QR Code</th>
              <th style={thStyle}>Name</th>
              <th style={thStyle}>Images</th>
              <th style={thStyle}>Area (mm&sup2;)</th>
              <th style={thStyle}>Health</th>
              <th style={thStyle}>Status</th>
            </tr>
          </thead>
          <tbody>
            {plants.map((p) => (
              <tr
                key={p.id}
                style={{ borderBottom: "1px solid #eee" }}
              >
                <td style={tdStyle}>
                  <Link
                    to={`/plants/${p.id}`}
                    style={{ color: "#1e88e5", textDecoration: "none" }}
                  >
                    {p.qr_code}
                  </Link>
                </td>
                <td style={tdStyle}>{p.name ?? "—"}</td>
                <td style={tdStyle}>{p.image_count}</td>
                <td style={tdStyle}>
                  {p.latest_area_mm2 != null
                    ? p.latest_area_mm2.toFixed(1)
                    : "—"}
                </td>
                <td style={tdStyle}>
                  <HealthBadge score={p.latest_health_score} />
                </td>
                <td style={tdStyle}>
                  {p.latest_is_overgrown && (
                    <span
                      style={{
                        background: "#e53935",
                        color: "#fff",
                        padding: "2px 8px",
                        borderRadius: 10,
                        fontSize: 12,
                        fontWeight: 600,
                      }}
                    >
                      OVERGROWN
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function HealthBadge({ score }: { score: number | null }) {
  if (score == null) return <span>—</span>;

  let bg = "#4caf50";
  if (score < 40) bg = "#e53935";
  else if (score < 70) bg = "#ffb300";

  return (
    <span
      style={{
        background: bg,
        color: "#fff",
        padding: "2px 10px",
        borderRadius: 10,
        fontSize: 12,
        fontWeight: 600,
      }}
    >
      {score.toFixed(0)}
    </span>
  );
}

const thStyle: React.CSSProperties = { padding: "10px 12px", fontWeight: 600 };
const tdStyle: React.CSSProperties = { padding: "10px 12px" };
