import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchPlant, type PlantDetail as PlantDetailType } from "../api/client";
import AlertBanner from "../components/AlertBanner";
import ImageSlider from "../components/ImageSlider";
import TimeSeriesChart from "../components/TimeSeriesChart";

export default function PlantDetail() {
  const { id } = useParams<{ id: string }>();
  const [plant, setPlant] = useState<PlantDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    fetchPlant(Number(id))
      .then(setPlant)
      .catch((err) => setError(err.message ?? "Failed to load plant"))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <p>Loading...</p>;
  if (error) return <AlertBanner type="danger" message={error} />;
  if (!plant) return <AlertBanner type="danger" message="Plant not found" />;

  // Prepare chart data
  const sortedMeasurements = [...plant.measurements].sort(
    (a, b) => new Date(a.measured_at).getTime() - new Date(b.measured_at).getTime()
  );

  const areaData = sortedMeasurements.map((m) => ({
    label: new Date(m.measured_at).toLocaleDateString(),
    value: m.area_mm2 ?? m.area_px,
  }));

  const healthData = sortedMeasurements.map((m) => ({
    label: new Date(m.measured_at).toLocaleDateString(),
    value: m.health_score,
  }));

  const latest = sortedMeasurements[sortedMeasurements.length - 1];
  const hasOvergrowth = latest?.is_overgrown ?? false;
  const hasLowHealth = (latest?.health_score ?? 100) < 40;

  // Sort images chronologically for the slider
  const sortedImages = [...plant.images].sort(
    (a, b) => new Date(a.captured_at).getTime() - new Date(b.captured_at).getTime()
  );

  return (
    <div>
      <Link
        to="/"
        style={{ color: "#1e88e5", textDecoration: "none", fontSize: 14 }}
      >
        &larr; Back to Plants
      </Link>

      <h1 style={{ margin: "12px 0 4px", fontSize: 24 }}>
        {plant.name ?? plant.qr_code}
      </h1>
      <p style={{ color: "#888", margin: "0 0 16px", fontSize: 14 }}>
        QR: {plant.qr_code} &middot; {plant.images.length} image(s)
      </p>

      {/* Alerts */}
      {hasOvergrowth && (
        <AlertBanner
          type="danger"
          message={`Overgrowth detected! Latest area: ${latest.area_mm2?.toFixed(1) ?? "?"} mm\u00B2`}
        />
      )}
      {hasLowHealth && (
        <AlertBanner
          type="warning"
          message={`Low health score: ${latest.health_score.toFixed(0)}/100`}
        />
      )}

      {/* Charts side by side on wide screens */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))",
          gap: 24,
        }}
      >
        <TimeSeriesChart
          data={areaData}
          title={`Plant Area (${latest?.area_mm2 != null ? "mm\u00B2" : "px"})`}
          color="#2196f3"
          yLabel={latest?.area_mm2 != null ? "mm\u00B2" : "px"}
        />
        <TimeSeriesChart
          data={healthData}
          title="Health Score"
          color="#4caf50"
          yLabel="Score (0–100)"
        />
      </div>

      {/* Latest metrics table */}
      {latest && (
        <div style={{ marginBottom: 24 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>
            Latest Metrics
          </h3>
          <table
            style={{
              borderCollapse: "collapse",
              fontSize: 14,
              width: "100%",
              maxWidth: 500,
            }}
          >
            <tbody>
              {[
                ["Area (px)", latest.area_px.toLocaleString()],
                [
                  "Area (mm\u00B2)",
                  latest.area_mm2 != null ? latest.area_mm2.toFixed(1) : "N/A",
                ],
                ["px/mm", latest.px_per_mm != null ? latest.px_per_mm.toFixed(2) : "N/A"],
                ["Mean Hue", latest.mean_hue.toFixed(1)],
                ["Saturation", latest.mean_saturation.toFixed(3)],
                ["Greenness", latest.greenness_index.toFixed(3)],
                ["Health Score", latest.health_score.toFixed(1)],
                [
                  "Growth Rate",
                  latest.growth_rate != null
                    ? `${latest.growth_rate.toFixed(2)} mm\u00B2/h`
                    : "N/A",
                ],
              ].map(([label, val]) => (
                <tr key={label} style={{ borderBottom: "1px solid #eee" }}>
                  <td
                    style={{
                      padding: "6px 12px",
                      fontWeight: 500,
                      color: "#555",
                    }}
                  >
                    {label}
                  </td>
                  <td style={{ padding: "6px 12px" }}>{val}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Image slider */}
      <ImageSlider images={sortedImages} />
    </div>
  );
}
