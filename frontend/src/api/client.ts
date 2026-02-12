import axios from "axios";

const api = axios.create({
  baseURL: "/api",
});

// ── Types ────────────────────────────────────────────────────────────

export interface PlantSummary {
  id: number;
  qr_code: string;
  name: string | null;
  created_at: string;
  latest_area_mm2: number | null;
  latest_health_score: number | null;
  latest_is_overgrown: boolean | null;
  image_count: number;
}

export interface Measurement {
  id: number;
  image_id: number;
  plant_id: number;
  area_px: number;
  area_mm2: number | null;
  px_per_mm: number | null;
  mean_hue: number;
  mean_saturation: number;
  greenness_index: number;
  health_score: number;
  growth_rate: number | null;
  is_overgrown: boolean;
  measured_at: string;
}

export interface ImageMeta {
  id: number;
  plant_id: number;
  filename: string;
  filepath: string;
  captured_at: string;
  uploaded_at: string;
  measurement: Measurement | null;
}

export interface PlantDetail {
  id: number;
  qr_code: string;
  name: string | null;
  created_at: string;
  images: ImageMeta[];
  measurements: Measurement[];
}

export interface AnalysisResult {
  images_processed: number;
  plants_found: number;
  errors: string[];
}

// ── API calls ────────────────────────────────────────────────────────

export async function fetchPlants(): Promise<PlantSummary[]> {
  const { data } = await api.get<PlantSummary[]>("/plants");
  return data;
}

export async function fetchPlant(id: number): Promise<PlantDetail> {
  const { data } = await api.get<PlantDetail>(`/plants/${id}`);
  return data;
}

export async function fetchMeasurements(plantId: number): Promise<Measurement[]> {
  const { data } = await api.get<Measurement[]>(`/plants/${plantId}/measurements`);
  return data;
}

export async function triggerAnalysis(imageDir?: string): Promise<AnalysisResult> {
  const { data } = await api.post<AnalysisResult>("/analyze", {
    image_dir: imageDir ?? null,
  });
  return data;
}

export function imageFileUrl(imageId: number): string {
  return `/api/images/${imageId}/file`;
}
