"use client";

export default function PanduanPage() {
  const closeGuide = () => {
    window.close();
  };

  return (
    <main className="h-screen overflow-y-auto bg-slate-50 text-slate-800">
      <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6 sm:py-12">
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={closeGuide}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-indigo-700"
          >
            <span aria-hidden="true">←</span> Kembali ke Dasbor
          </button>
        </div>

        <h1 className="mt-6 text-2xl font-bold text-slate-900 sm:text-3xl">
          Panduan Penggunaan
        </h1>
        <p className="mt-2 text-sm text-slate-500">
          AI Research &amp; Knowledge Synthesis Agent — cara mengunggah beberapa sumber
          sekaligus, bertanya, mengelola dokumen, dan mengekspor hasil riset.
        </p>

        <section className="mt-8 space-y-6">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">1. Mengunggah Sumber</h2>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-relaxed">
              <li>
                Seret &amp; jatuhkan atau pilih beberapa file sekaligus (PDF, DOCX, PPTX,
                atau TXT). Semua file yang dipilih bersama akan digabungkan ke dalam{" "}
                <strong>satu sesi obrolan yang sama</strong>, sehingga bisa dibahas secara
                kolektif.
              </li>
              <li>
                Maksimal 10MB per file. Saat unggahan berlangsung, panel menunjukkan status
                per file.
              </li>
              <li>
                Bisa juga menempelkan tautan jurnal/artikel pada kolom URL lalu klik{" "}
                <strong>Tambah</strong>.
              </li>
              <li>
                Gambar atau dokumen pindaian (scan) diproses otomatis dengan OCR agar teksnya
                dapat dicari.
              </li>
            </ul>
          </div>

          <div>
            <h2 className="text-lg font-semibold text-slate-900">2. Mengelola Dokumen</h2>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-relaxed">
              <li>
                Panel <strong>Dokumen Sumber</strong> menampilkan semua file pada sesi aktif.
              </li>
              <li>
                Klik ikon <strong>hapus (×)</strong> di samping sebuah file untuk menghapus
                file tersebut beserta semua indeks/vektornya tanpa memengaruhi sesi lainnya.
              </li>
            </ul>
          </div>

          <div>
            <h2 className="text-lg font-semibold text-slate-900">3. Mengajukan Pertanyaan</h2>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-relaxed">
              <li>
                Ketik pertanyaan pada kolom obrolan lalu tekan <strong>Kirim</strong>. Jawaban
                dihasilkan hanya dari sumber pada sesi aktif (yang digabungkan).
              </li>
              <li>
                Untuk membandingkan dengan materi tambahan, gunakan kata kunci seperti{" "}
                <em>“bandingkan”, “compare”, “perbedaan”</em>.
              </li>
              <li>
                Jika ingin menyertakan sitasi/referensi, minta secara eksplisit, misalnya{" "}
                <em>“berikan kutipan dan referensi”</em>.
              </li>
            </ul>
          </div>

          <div>
            <h2 className="text-lg font-semibold text-slate-900">4. Kelola Sesi dan Ekspor</h2>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-relaxed">
              <li>
                Panel <strong>Riwayat Riset</strong> menampilkan sesi-sesi Anda dengan
                timestamp real-time. Gunakan tombol <strong>+</strong> untuk sesi baru.
              </li>
              <li>
                Pada panel <strong>Ekspor</strong>, pilih format (PDF/Word) lalu klik tombol
                ekspor untuk mengunduh ringkasan riset sesi aktif.
              </li>
            </ul>
          </div>
        </section>
      </div>
    </main>
  );
}
