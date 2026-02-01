import { X, Maximize2 } from "lucide-react";
import type { ReactNode } from "react";

interface ChartModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}

export function ChartModal({ isOpen, onClose, title, children }: ChartModalProps) {
  if (!isOpen) return null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1000,
        background: "rgba(0, 0, 0, 0.85)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "var(--bg-secondary)",
          borderRadius: "var(--radius-md)",
          width: "100%",
          maxWidth: "95vw",
          maxHeight: "90vh",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "16px 20px",
            borderBottom: "1px solid var(--border-color)",
          }}
        >
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>{title}</h3>
          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              color: "var(--text-muted)",
              cursor: "pointer",
              padding: 4,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <X size={20} />
          </button>
        </div>
        {/* Chart content */}
        <div style={{ flex: 1, padding: 20, minHeight: "70vh" }}>
          {children}
        </div>
      </div>
    </div>
  );
}

interface ExpandButtonProps {
  onClick: () => void;
}

export function ExpandButton({ onClick }: ExpandButtonProps) {
  return (
    <button
      onClick={onClick}
      title="Expand chart"
      style={{
        background: "var(--bg-tertiary)",
        border: "1px solid var(--border-color)",
        borderRadius: "var(--radius-sm)",
        color: "var(--text-muted)",
        cursor: "pointer",
        padding: "6px 8px",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        transition: "all 0.15s ease",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.color = "var(--accent)";
        e.currentTarget.style.borderColor = "var(--accent)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.color = "var(--text-muted)";
        e.currentTarget.style.borderColor = "var(--border-color)";
      }}
    >
      <Maximize2 size={14} />
    </button>
  );
}
