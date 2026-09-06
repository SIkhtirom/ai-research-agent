"use client";

export type ExportFormat = "md" | "pdf" | "pptx";

interface ExportPanelProps {
  isExporting: boolean;
  onExport: (format: ExportFormat) => void;
}

const exportButtons: Array<{
  format: ExportFormat;
  label: string;
  fileType: string;
  description: string;
  accentClass: string;
  iconColor: string;
}> = [
  {
    format: "md",
    label: "Markdown",
    fileType: ".md",
    description: "Ringkasan & laporan versi teks",
    accentClass: "border-lime-beacon/60 hover:bg-lime-beacon/10",
    iconColor: "text-lime-beacon",
  },
  {
    format: "pdf",
    label: "PDF",
    fileType: ".pdf",
    description: "Dokumen siap cetak & bagikan",
    accentClass: "border-orchid-whisper/60 hover:bg-orchid-whisper/10",
    iconColor: "text-orchid-whisper",
  },
  {
    format: "pptx",
    label: "PPTX",
    fileType: ".pptx",
    description: "Presentasi slide untuk paparan",
    accentClass: "border-periwinkle-veil/60 hover:bg-periwinkle-veil/10",
    iconColor: "text-periwinkle-veil",
  },
];

export default function ExportPanel({
  isExporting,
  onExport,
}: ExportPanelProps) {
  return (
    <section className="rounded-sm border border-white/10 bg-carbon-panel p-5">
      <p className="font-mono text-caption uppercase tracking-tight text-periwinkle-veil">
        {"// EKSPOR"}
      </p>
      <h3 className="mt-1 text-base font-bold text-pure-signal">Ekspor Hasil</h3>
      <p className="mt-1 text-sm leading-relaxed text-soft-mist/70">
        Unduh hasil riset dalam format yang Anda butuhkan.
      </p>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {exportButtons.map((button) => (
          <button
            key={button.format}
            type="button"
            onClick={() => onExport(button.format)}
            disabled={isExporting}
            className={`flex flex-col items-start rounded-sm border p-4 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${button.accentClass}`}
          >
            <span className={`text-sm font-bold ${button.iconColor}`}>
              {button.label}
            </span>
            <span className="mt-0.5 font-mono text-caption uppercase tracking-tight text-soft-mist/45">
              {button.fileType}
            </span>
            <span className="mt-2 text-xs leading-relaxed text-soft-mist/70">
              {button.description}
            </span>
          </button>
        ))}
      </div>

      {isExporting && (
        <p className="mt-3 font-mono text-caption uppercase tracking-tight text-periwinkle-veil">
          Menyiapkan ekspor…
        </p>
      )}
    </section>
  );
}