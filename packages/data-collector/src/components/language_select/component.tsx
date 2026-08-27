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
    </div>
  );
};
