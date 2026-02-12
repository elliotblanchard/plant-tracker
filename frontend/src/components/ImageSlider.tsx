import { useState } from "react";
import { imageFileUrl, type ImageMeta } from "../api/client";

interface ImageSliderProps {
  images: ImageMeta[];
}

export default function ImageSlider({ images }: ImageSliderProps) {
  const [index, setIndex] = useState(images.length - 1);

  if (images.length === 0) {
    return <p style={{ color: "#888" }}>No images available.</p>;
  }

  const current = images[index];
  const date = new Date(current.captured_at).toLocaleString();

  return (
    <div style={{ marginBottom: 24 }}>
      <h3 style={{ margin: "0 0 8px", fontSize: 16, fontWeight: 600 }}>
        Image Timeline
      </h3>

      <div
        style={{
          border: "1px solid #e0e0e0",
          borderRadius: 8,
          overflow: "hidden",
          backgroundColor: "#fafafa",
          textAlign: "center",
        }}
      >
        <img
          src={imageFileUrl(current.id)}
          alt={current.filename}
          style={{ maxWidth: "100%", maxHeight: 400, objectFit: "contain" }}
        />
        <div style={{ padding: "8px 12px", fontSize: 13, color: "#555" }}>
          {current.filename} &mdash; {date}
        </div>
      </div>

      {/* Slider control */}
      <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 12 }}>
        <span style={{ fontSize: 12, color: "#888" }}>Oldest</span>
        <input
          type="range"
          min={0}
          max={images.length - 1}
          value={index}
          onChange={(e) => setIndex(Number(e.target.value))}
          style={{ flex: 1 }}
        />
        <span style={{ fontSize: 12, color: "#888" }}>Newest</span>
      </div>

      {/* Thumbnail strip */}
      <div
        style={{
          display: "flex",
          gap: 4,
          overflowX: "auto",
          marginTop: 8,
          paddingBottom: 4,
        }}
      >
        {images.map((img, i) => (
          <img
            key={img.id}
            src={imageFileUrl(img.id)}
            alt={img.filename}
            onClick={() => setIndex(i)}
            style={{
              width: 56,
              height: 56,
              objectFit: "cover",
              borderRadius: 4,
              cursor: "pointer",
              border: i === index ? "2px solid #4caf50" : "2px solid transparent",
              opacity: i === index ? 1 : 0.6,
            }}
          />
        ))}
      </div>
    </div>
  );
}
