"use client";

import { useState } from "react";

const navigationLinks = [
  { label: "Beranda", href: "#" },
  { label: "Unggah Dokumen", href: "#" },
  { label: "Bantuan", href: "#" },
];

export default function Navbar() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/80 backdrop-blur">
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
        <a href="#" className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">
            AI
          </span>
          <span className="text-base font-semibold text-slate-900">
            AI Research &amp; Knowledge Synthesis Agent
          </span>
        </a>

        <div className="hidden items-center gap-6 sm:flex">
          {navigationLinks.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="text-sm font-medium text-slate-600 transition-colors hover:text-indigo-600"
            >
              {link.label}
            </a>
          ))}
          <a
            href="#"
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-indigo-700"
          >
            Mulai Riset
          </a>
        </div>

        <button
          type="button"
          aria-label="Buka menu navigasi"
          onClick={() => setIsMenuOpen((open) => !open)}
          className="rounded-md p-2 text-slate-700 hover:bg-slate-100 sm:hidden"
        >
          <svg
            className="h-6 w-6"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M4 6h16M4 12h16M4 18h16"
            />
          </svg>
        </button>
      </nav>

      {isMenuOpen && (
        <div className="border-t border-slate-200 bg-white px-4 py-3 sm:hidden">
          <div className="flex flex-col gap-3">
            {navigationLinks.map((link) => (
              <a
                key={link.label}
                href={link.href}
                className="text-sm font-medium text-slate-700 hover:text-indigo-600"
              >
                {link.label}
              </a>
            ))}
            <a
              href="#"
              className="rounded-lg bg-indigo-600 px-4 py-2 text-center text-sm font-semibold text-white"
            >
              Mulai Riset
            </a>
          </div>
        </div>
      )}
    </header>
  );
}
