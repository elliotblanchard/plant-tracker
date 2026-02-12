interface AlertBannerProps {
  type: "warning" | "danger" | "info";
  message: string;
}

export default function AlertBanner({ type, message }: AlertBannerProps) {
  const colors: Record<string, { bg: string; border: string; text: string }> = {
    warning: { bg: "#fff8e1", border: "#ffb300", text: "#6d4c00" },
    danger: { bg: "#fce4ec", border: "#e53935", text: "#b71c1c" },
    info: { bg: "#e3f2fd", border: "#1e88e5", text: "#0d47a1" },
  };

  const c = colors[type] ?? colors.info;

  return (
    <div
      style={{
        padding: "10px 16px",
        marginBottom: 12,
        borderLeft: `4px solid ${c.border}`,
        backgroundColor: c.bg,
        color: c.text,
        borderRadius: 4,
        fontSize: 14,
      }}
    >
      {message}
    </div>
  );
}
