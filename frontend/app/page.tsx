import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "AI Research & Knowledge Synthesis Agent",
  description:
    "Agen AI untuk mengumpulkan banyak sumber, mengajukan pertanyaan lintas dokumen, dan mengekspor hasil riset yang bersitasi.",
};

const features = [
  {
    number: "01",
    title: "Unggah Sumber",
    body: "Kumpulkan PDF, DOCX, PPTX, TXT, atau tautan web dalam satu sesi. Unggah banyak file sekaligus dan biarkan semuanya diindeks menjadi satu konteks riset.",
  },
  {
    number: "02",
    title: "Tanya Asisten",
    body: "Ajukan pertanyaan apa pun dan terima jawaban yang disintesis langsung dari sumber Anda, lengkap dengan kutipan yang dapat ditelusuri kembali.",
  },
  {
    number: "03",
    title: "Ekspor Hasil",
    body: "Unduh ringkasan riset dalam format pilihan Anda — Markdown, PDF siap cetak, atau slide presentasi — cukup dengan satu klik.",
  },
];

const steps = [
  {
    number: "01",
    title: "Kumpulkan",
    body: "Unggah file dan tautan sumber ke dalam satu sesi riset yang terorganisir.",
  },
  {
    number: "02",
    title: "Tanyakan",
    body: "Diskusikan lintas sumber dengan asisten yang menjawab berdasarkan kutipan nyata.",
  },
  {
    number: "03",
    title: "Ekspor",
    body: "Simpan ringkasan riset sesuai format yang Anda butuhkan, kapan saja.",
  },
];

export default function LandingPage() {
  return (
    <main className="h-screen scroll-smooth overflow-y-auto bg-midnight-void text-soft-mist">
      <header className="sticky top-0 z-50 border-b border-white/10 bg-midnight-void/90 backdrop-blur">
        <nav className="mx-auto flex max-w-[1200px] items-center justify-between px-6 py-5">
          <a href="#" className="flex items-center gap-3">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-sm bg-electric-indigo text-sm font-bold text-pure-signal">
              AI
            </span>
            <span className="hidden text-sm font-bold tracking-tight text-pure-signal sm:block">
              AI Research &amp; Knowledge Synthesis Agent
            </span>
          </a>

          <div className="hidden items-center gap-8 md:flex">
            <a href="#fitur" className="text-sm font-medium text-soft-mist/70 transition-colors hover:text-pure-signal">
              Fitur
            </a>
            <a href="#cara-kerja" className="text-sm font-medium text-soft-mist/70 transition-colors hover:text-pure-signal">
              Cara Kerja
            </a>
            <Link href="/panduan" target="_blank" rel="noopener" className="text-sm font-medium text-soft-mist/70 transition-colors hover:text-pure-signal">
              Panduan
            </Link>
          </div>

          <Link
            href="/app"
            className="rounded-sm bg-electric-indigo px-4 py-2 text-sm font-bold text-pure-signal transition-colors hover:bg-cobalt-pulse"
          >
            Launch App
            <span aria-hidden="true" className="ml-1">→</span>
          </Link>
        </nav>
      </header>

      <section className="mx-auto max-w-[1200px] px-6 pb-24 pt-20 sm:pb-32 sm:pt-28">
        <p className="animate-fade-in-up font-mono text-caption uppercase tracking-tight text-periwinkle-veil">
          Agen Sintesis Pengetahuan Berbasis AI
        </p>
        <h1
          className="animate-fade-in-up mt-6 max-w-4xl text-4xl font-bold leading-[1.05] tracking-tight text-pure-signal sm:text-6xl lg:text-7xl"
          style={{ animationDelay: "80ms" }}
        >
          Riset Anda,
          <br className="hidden sm:block" /> disintesis oleh{" "}
          <span className="text-periwinkle-veil">AI Anda</span>.
        </h1>
        <p
          className="animate-fade-in-up mt-6 max-w-2xl text-base leading-relaxed text-soft-mist/75 sm:text-lg"
          style={{ animationDelay: "160ms" }}
        >
          Kumpulkan semua sumber di satu tempat, ajukan pertanyaan lintas dokumen,
          dan terima jawaban yang bersitasi — bukan sekadar dugaan. Dari pengumpulan
          hingga ekspor, satu alur kerja riset yang utuh.
        </p>
        <div
          className="animate-fade-in-up mt-10 flex flex-wrap items-center gap-4"
          style={{ animationDelay: "240ms" }}
        >
          <Link
            href="/app"
            className="rounded-sm bg-electric-indigo px-6 py-3.5 text-sm font-bold text-pure-signal transition-colors hover:bg-cobalt-pulse"
          >
            Launch App
            <span aria-hidden="true" className="ml-2">→</span>
          </Link>
          <Link
            href="/panduan"
            target="_blank"
            rel="noopener"
            className="rounded-sm border border-white/20 px-6 py-3.5 text-sm font-semibold text-soft-mist transition-colors hover:bg-graphite-lift"
          >
            Lihat Panduan
          </Link>
        </div>
        <p
          className="animate-fade-in-up mt-10 font-mono text-caption uppercase tracking-tight text-soft-mist/40"
          style={{ animationDelay: "320ms" }}
        >
          Mendukung PDF · DOCX · PPTX · TXT · URL
        </p>
      </section>

      <section id="fitur" className="scroll-mt-20 border-t border-white/10">
        <div className="mx-auto max-w-[1200px] px-6 py-16 sm:py-20">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <h2 className="max-w-xl text-2xl font-bold tracking-tight text-pure-signal sm:text-3xl">
              Dari sumber mentah menjadi hasil jadi.
            </h2>
            <p className="max-w-md text-sm leading-relaxed text-soft-mist/65">
              Tiga kemampuan inti yang menghubungkan dokumen Anda dengan wawasan yang bisa
              langsung dipakai.
            </p>
          </div>

          <div className="mt-10 grid grid-cols-1 gap-5 md:grid-cols-3">
            {features.map((feature) => (
              <div
                key={feature.number}
                className="rounded-sm border border-white/10 bg-carbon-panel p-6 transition-colors hover:border-periwinkle-veil/50 hover:bg-graphite-lift/40"
              >
                <p className="font-mono text-caption uppercase tracking-tight text-periwinkle-veil">
                  {feature.number}
                </p>
                <h3 className="mt-3 text-lg font-bold text-pure-signal">{feature.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-soft-mist/70">{feature.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="cara-kerja" className="scroll-mt-20 border-t border-white/10">
        <div className="mx-auto max-w-[1200px] px-6 py-16 sm:py-20">
          <h2 className="max-w-xl text-2xl font-bold tracking-tight text-pure-signal sm:text-3xl">
            Cara kerjanya sederhana.
          </h2>
          <ol className="mt-10 grid grid-cols-1 gap-8 sm:grid-cols-3 sm:gap-6">
            {steps.map((step) => (
              <li key={step.number} className="flex flex-col gap-3">
                <span className="font-mono text-caption uppercase tracking-tight text-soft-mist/40">
                  Langkah {step.number}
                </span>
                <div className="border-t border-white/15 pt-4">
                  <h3 className="text-lg font-bold text-pure-signal">{step.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-soft-mist/70">{step.body}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="border-t border-white/10 bg-carbon-panel">
        <div className="mx-auto flex max-w-[1200px] flex-col items-start justify-between gap-6 px-6 py-16 sm:flex-row sm:items-center sm:py-20">
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-pure-signal sm:text-3xl">
              Siap memulai riset?
            </h2>
            <p className="mt-2 max-w-lg text-sm leading-relaxed text-soft-mist/65">
              Gabungkan semua sumber Anda, tanyakan apa saja, dan ekspor hasilnya dalam
              hitungan menit.
            </p>
          </div>
          <Link
            href="/app"
            className="shrink-0 rounded-sm bg-electric-indigo px-7 py-3.5 text-sm font-bold text-pure-signal transition-colors hover:bg-cobalt-pulse"
          >
            Launch App
            <span aria-hidden="true" className="ml-2">→</span>
          </Link>
        </div>
      </section>

      <footer className="border-t border-white/10">
        <div className="mx-auto flex max-w-[1200px] flex-col gap-4 px-6 py-8 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-sm bg-electric-indigo text-xs font-bold text-pure-signal">
              AI
            </span>
            <span className="text-sm font-semibold text-soft-mist">
              AI Research &amp; Knowledge Synthesis Agent
            </span>
          </div>
          <div className="flex items-center gap-6">
            <Link
              href="/panduan"
              target="_blank"
              rel="noopener"
              className="text-xs text-soft-mist/55 transition-colors hover:text-pure-signal"
            >
              Panduan
            </Link>
            <Link
              href="/hak-privasi"
              target="_blank"
              rel="noopener"
              className="text-xs text-soft-mist/55 transition-colors hover:text-pure-signal"
            >
              Hak &amp; Privasi
            </Link>
          </div>
          <p className="text-xs text-soft-mist/40">© 2026</p>
        </div>
      </footer>
    </main>
  );
}