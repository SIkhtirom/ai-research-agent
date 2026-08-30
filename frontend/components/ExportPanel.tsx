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
    accentClass: "hover:border-emerald-300 hover:bg-emerald-50",
    iconColor: "text-emerald-600",
  },
  {
    format: "pdf",
    label: "PDF",
    fileType: ".pdf",
    description: "Dokumen siap cetak & bagikan",
    accentClass: "hover:border-rose-300 hover:bg-rose-50",
    iconColor: "text-rose-600",
  },
  {
    format: "pptx",
    label: "PPTX",
    fileType: ".pptx",
    description: "Presentasi slide untuk paparan",
    accentClass: "hover:border-amber-300 hover:bg-amber-50",
    iconColor: "text-amber-600",
  },
];

export default function ExportPanel({
  isExporting,
  onExport,
}: ExportPanelProps) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold text-slate-900">Ekspor Hasil</h3>
      <p className="mt-1 text-sm text-slate-500">
        Unduh hasil riset dalam format yang Anda butuhkan.
      </p>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {exportButtons.map((button) => (
          <button
            key={button.format}
            type="button"
            onClick={() => onExport(button.format)}
            disabled={isExporting}
            className={`flex flex-col items-start rounded-xl border border-slate-200 p-4 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${button.accentClass}`}
          >
            <span className={`text-sm font-bold ${button.iconColor}`}>
              {button.label}
            </span>
            <span className="mt-0.5 text-xs text-slate-400">{button.fileType}</span>
            <span className="mt-2 text-xs leading-relaxed text-slate-600">
              {button.description}
            </span>
          </button>
        ))}
      </div>

      {isExporting && (
        <p className="mt-3 text-xs text-slate-400">Menyiapkan ekspor…</p>
      )}
    </section>
  );
}
