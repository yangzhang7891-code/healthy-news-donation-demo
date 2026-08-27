import React from "react";

// Landing screen shown before the donation flow mounts. Kiosk-sized
// touch targets (large buttons, generous spacing) since this runs on
// a tablet at a physical stand, not a desktop browser. Plain and
// calm on purpose: no logos, no marketing language, just the choice
// a participant needs to make before anything else happens.

interface Props {
  onSelect: (locale: "en" | "da") => void;
}

export const LanguageSelect: React.FC<Props> = ({ onSelect }) => {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-10 bg-white px-6 text-center">
      <div className="max-w-xl">
        <h1 className="text-3xl font-semibold text-gray-900 sm:text-4xl">
          Choose your language
          <br />
          Vælg dit sprog
        </h1>
      </div>
      <div className="flex w-full max-w-xl flex-col gap-6 sm:flex-row">
        <button
          type="button"
          onClick={() => onSelect("en")}
          className="flex-1 rounded-lg border-2 border-gray-200 bg-white px-8 py-10 text-2xl font-medium text-gray-900 shadow-sm transition-colors hover:bg-gray-50 focus:outline-none focus-visible:ring-4 focus-visible:ring-blue-500 active:bg-gray-100"
          aria-label="Continue in English"
        >
          English
        </button>
        <button
          type="button"
          onClick={() => onSelect("da")}
          className="flex-1 rounded-lg border-2 border-gray-200 bg-white px-8 py-10 text-2xl font-medium text-gray-900 shadow-sm transition-colors hover:bg-gray-50 focus:outline-none focus-visible:ring-4 focus-visible:ring-blue-500 active:bg-gray-100"
          aria-label="Fortsæt på dansk"
        >
          Dansk
        </button>
      </div>
      <SampleDownloads />
    </div>
  );
};

// Visitors to the public demo won't have their own platform export to
// hand — a real one takes hours or days to arrive. Without something to
// upload, "try it" stops at the file picker. These are the same
// synthetic fixtures the test suite runs against: no real person's data,
// and deliberately including the wrong-format case, since the
// JSON-vs-HTML mistake is the one this project spends the most effort
// detecting and is worth being able to see happen.
const SAMPLES = [
  { file: "sample-youtube-news-heavy.zip", label: "YouTube — news-heavy donor" },
  { file: "sample-tiktok.zip", label: "TikTok — mixed donor" },
  { file: "sample-instagram-danish.zip", label: "Instagram — Danish, mangled encoding" },
  { file: "sample-youtube-wrong-format-html.zip", label: "YouTube — wrong format (HTML)" },
];

const SampleDownloads: React.FC = () => (
  <div className="max-w-xl border-t border-gray-200 pt-6 text-sm text-gray-600">
    <p className="mb-3">
      No export of your own? Download a synthetic sample to try it with.
      <span className="block text-xs text-gray-500">
        Ingen egen dataeksport? Hent et syntetisk eksempel at afprøve med.
      </span>
    </p>
    <ul className="flex flex-wrap justify-center gap-x-4 gap-y-2">
      {SAMPLES.map((s) => (
        <li key={s.file}>
          <a
            className="rounded underline underline-offset-2 hover:text-gray-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            href={`./samples/${s.file}`}
            download
          >
            {s.label}
          </a>
        </li>
      ))}
    </ul>
  </div>
);
