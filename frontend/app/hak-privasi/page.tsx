"use client";

export default function HakPrivasiPage() {
  const closeGuide = () => {
    window.close();
  };

  return (
    <main className="h-screen overflow-y-auto bg-midnight-void text-soft-mist">
      <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6 sm:py-12">
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={closeGuide}
            className="inline-flex items-center gap-2 rounded-sm bg-electric-indigo px-4 py-2 text-sm font-bold text-pure-signal transition-colors hover:bg-cobalt-pulse"
          >
            <span aria-hidden="true">←</span> Kembali ke Dasbor
          </button>
        </div>

        <p className="mt-10 font-mono text-caption uppercase tracking-tight text-periwinkle-veil">
          {"// PRIVASI"}
        </p>
        <h1 className="mt-2 text-2xl font-bold tracking-tight text-pure-signal sm:text-3xl">
          Hak &amp; Privasi
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-soft-mist/70">
          Informasi hak penggunaan dan kebijakan privasi pada AI Research &amp; Knowledge
          Synthesis Agent.
        </p>

        <section className="mt-8 space-y-6">
          <div className="rounded-sm border border-white/10 bg-carbon-panel p-5">
            <h2 className="text-lg font-semibold text-pure-signal">Hak Pengguna</h2>
            <p className="mt-2 text-sm leading-relaxed text-soft-mist/80">
              Anda berhak menggunakan platform ini secara bijak dan bertanggung jawab.
              Platform disediakan untuk membantu proses riset, analisis, dan penyusunan
              ringkasan secara efisien. Gunakan seluruh fitur sesuai ketentuan yang berlaku,
              hormati hak kekayaan intelektual orang lain, dan hindari menyalahgunakan alat
              ini untuk hal-hal yang tidak etis atau melanggar hukum.
            </p>
          </div>

          <div className="rounded-sm border border-white/10 bg-carbon-panel p-5">
            <h2 className="text-lg font-semibold text-pure-signal">Privasi Data</h2>
            <p className="mt-2 text-sm leading-relaxed text-soft-mist/80">
              Sistem <strong className="text-pure-signal">tidak menyimpan repository (berkas) file yang Anda unggah</strong>.
              File yang diunggah hanya diproses sebagai sesi sementara secara lokal untuk
              keperluan ekstraksi teks, pencarian konteks, dan sintesis jawaban. Setelah
              sesi digunakan, berkas asli Anda tidak diarsipkan sebagai gudang data permanen
              oleh platform ini.
            </p>
          </div>

          <div className="rounded-sm border border-white/10 bg-carbon-panel p-5">
            <h2 className="text-lg font-semibold text-pure-signal">Jaminan Kami</h2>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-relaxed text-soft-mist/80">
              <li>Tidak ada pengumpulan data pribadi di luar keperluan teknis sesi.</li>
              <li>Berkas yang diunggah tidak dibagikan kepada pihak ketiga.</li>
              <li>Anda dapat menghapus dokumen dari sesi aktif kapan saja.</li>
              <li>Gunakan platform dengan bijak dan sesuai dengan peraturan yang berlaku.</li>
            </ul>
          </div>
        </section>
      </div>
    </main>
  );
}