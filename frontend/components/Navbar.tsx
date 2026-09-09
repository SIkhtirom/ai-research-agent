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
    <header className="sticky top-0 z-50 border-b border-white/10 bg-midnight-void/90 backdrop-blur">
      <nav className="mx-auto flex max-w-[1200px] items-center justify-between px-6 py-[22px]">
        <a href="#" className="flex items-center gap-3">
          {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
            src="/logo-header.png"
            alt="Logo AI Research &amp; Knowledge Synthesis Agent"
            className="h-8 w-8 shrink-0 rounded-sm object-contain"
          />
          <span className="text-base font-bold tracking-tight text-pure-signal">
            AI Research &amp; Knowledge Synthesis Agent
          </span>
        </a>

        <div className="hidden items-center gap-7 sm:flex">
          {navigationLinks.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="font-mono text-caption uppercase tracking-tight text-soft-mist transition-colors hover:text-pure-signal"
            >
              • {link.label}
            </a>
          ))}
          <a
            href="#"
            className="rounded-sm bg-electric-indigo px-4 py-2 text-sm font-bold text-pure-signal transition-colors hover:bg-cobalt-pulse"
          >
            Mulai Riset
          </a>
        </div>

        <button
          type="button"
          aria-label="Buka menu navigasi"
          onClick={() => setIsMenuOpen((open) => !open)}
          className="rounded-sm p-2 text-soft-mist hover:bg-graphite-lift sm:hidden"
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
        <div className="border-t border-white/10 bg-carbon-panel px-4 py-3 sm:hidden">
          <div className="flex flex-col gap-3">
            {navigationLinks.map((link) => (
              <a
                key={link.label}
                href={link.href}
                className="font-mono text-caption uppercase tracking-tight text-soft-mist hover:text-pure-signal"
              >
                • {link.label}
              </a>
            ))}
            <a
              href="#"
              className="rounded-sm bg-electric-indigo px-4 py-2 text-center text-sm font-bold text-pure-signal"
            >
              Mulai Riset
            </a>
          </div>
        </div>
      )}
    </header>
  );
}