# Product Requirements Document (PRD)
**Project Name:** AI Research & Knowledge Synthesis Agent  
**Event:** AI Hackfest 2026 by IDwebhost  
**Target Category:** Productivity & Personal AI / Open Innovation  

## 1. Project Overview
Aplikasi ini adalah *AI Agent* cerdas yang dirancang untuk mengatasi inefisiensi dalam proses riset. Agent ini menerima pertanyaan atau instruksi kompleks dari pengguna, lalu secara otomatis mengumpulkan, mengekstrak, mensintesis informasi dari berbagai sumber (file PDF, DOCX, PPT, TXT, dan URL website/link jurnal), dan menghasilkan *output* terstruktur (laporan, ringkasan, atau presentasi).
**Value Proposition:** Mengubah 8 jam proses membaca dan merangkum manual menjadi 5 menit analisis komprehensif.

## 2. Spesifikasi Teknologi (Tech Stack)
*PENTING BAGI AI ASSISTANT: Patuhi stack berikut secara ketat, jangan gunakan alternatif lain tanpa instruksi eksplisit.*

*   **Frontend:** Next.js (App Router), React, Tailwind CSS, TypeScript.
*   **Backend / API:** Python dengan FastAPI.
*   **AI Orchestration:** LangChain atau LlamaIndex (untuk RAG Pipeline).
*   **Vector Database:** ChromaDB atau FAISS.
*   **LLM Engine:** OpenAI API atau Gemini API.
*   **Data Ingestion & Parsing:**
    *   PDF: `pypdf` dan `marker`.
    *   Word (DOCX): `python-docx`.
    *   PowerPoint (PPT/PPTX): `python-pptx`.
    *   Text (TXT): Native Python I/O.
    *   Web/URL Scraping (Website & Jurnal): `requests`, `BeautifulSoup` (atau LangChain WebBaseLoader).
*   **External Integrations:** SerpAPI/Google Search API (opsional untuk pencarian web lanjutan).
*   **Export:** `python-pptx` (PowerPoint), Markdown to PDF parser.
*   **Deployment Target:** VPS (4 Core CPU, 4GB RAM) berbasis Linux/Docker.

## 3. Arsitektur Data & Model Utama
*   **Session/Chat:** `id`, `user_id`, `created_at`, `title`.
*   **Document (Knowledge Base):** `id`, `session_id`, `source_type` (pdf | docx | ppt | txt | url), `content_text`, `metadata` (url, filename, author, title), `vector_id`.
*   **Query Log:** `id`, `session_id`, `prompt`, `generated_response`, `citations` (array of Document IDs).

## 4. Alur Pengguna (User Flow)
1. **Upload & Ingestion:** User masuk ke *dashboard*, lalu bisa mengunggah file multi-format (PDF, DOCX, PPT, TXT) ATAU memasukkan URL (link artikel website atau jurnal).
2. **Processing:** Sistem mengenali format input secara dinamis, melakukan ekstraksi teks sesuai format -> *chunking* -> *embedding* -> simpan ke Vector DB.
3. **Querying:** User memasukkan *prompt* (contoh: "Tolong buatkan perbandingan metode dari 3 jurnal yang saya upload ini").
4. **Synthesis (RAG):** Backend mencari konteks yang relevan di Vector DB, menggabungkannya dengan *prompt*, lalu mengirimkannya ke LLM.
5. **Output Generation:** Sistem menampilkan hasil sintesis dilengkapi dengan **kutipan langsung** (citations) dari dokumen sumber (menyebutkan nama file atau URL asal).
6. **Export:** User dapat mengunduh hasil dalam format Markdown, PDF, atau presentasi .pptx.

## 5. Daftar Fitur Prioritas (MVP Scope untuk 8 Hari)
*   **[FITUR 1] Universal Ingestion Engine:** Endpoint FastAPI (multi-part form) untuk mendeteksi tipe file dan mengekstrak teks dari PDF, DOCX, PPT, TXT, dan URL secara dinamis.
*   **[FITUR 2] RAG Pipeline:** Logika LangChain/LlamaIndex untuk mencari teks yang relevan dari Vector DB berdasarkan pertanyaan *user*.
*   **[FITUR 3] Interactive Dashboard (Next.js):** UI drag-and-drop untuk unggah multi-file dan input URL, serta *chat interface* untuk berinteraksi dengan agen.
*   **[FITUR 4] Citation System:** Setiap klaim di jawaban LLM harus secara spesifik merujuk pada dokumen sumber asal (mengurangi halusinasi).
*   **[FITUR 5] Export to Document:** Tombol untuk mengubah hasil *chat/summary* menjadi file PDF atau PPT yang siap diunduh.

## 6. Coding Guidelines & AI Instructions
*Bertindaklah sebagai Senior Software Engineer. Saat menulis kode berdasarkan PRD ini, patuhi aturan berikut:*
1. **Clean Architecture:** Pisahkan *controller/routing* (FastAPI/Next.js) dengan *business logic* (RAG/Data Processing). 
2. **Modular Ingestion:** Buat arsitektur parser menggunakan *Factory Pattern* atau modul terpisah (misal: `parsers/pdf_parser.py`, `parsers/docx_parser.py`, `parsers/url_scraper.py`). Jangan gabung semua logika ekstraksi di satu file.
3. **Minimalis & Efisien:** Ingat batasan server (4GB RAM). Hindari memuat *model embedding* berukuran masif ke dalam memori secara berlebihan.
4. **Self-Documenting Code:** Hindari komentar berulang untuk logika yang sudah jelas.
5. **Error Handling:** Pastikan ada validasi tipe file di frontend dan backend. Berikan pesan *error* jika URL diblokir oleh anti-bot atau file *corrupt*.
6. **LANGUAGE RULES (SANGAT PENTING):** 
    * Seluruh *source code* (nama file, fungsi, variabel, tabel database, komentar kode) **WAJIB** ditulis dalam **Bahasa Inggris** yang standar.
    * Seluruh *User Interface* (teks di web, label tombol, pesan notifikasi, placeholder) **WAJIB** ditulis dalam **Bahasa Indonesia**.