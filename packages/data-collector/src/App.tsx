import { useMemo, useState } from "react";
import { DataSubmissionPageFactory, ScriptHostComponent } from "@eyra/feldspar";
import { LanguageSelect } from "./components/language_select/component";
import { DownloadBridge } from "./download_bridge";

// Every PropsUI* type script.py actually uses (radio input, file
// input, confirm, text, consent table, submission buttons) is covered
// by Feldspar's own default prompt factories — no custom factory
// needed here, unlike upstream's HelloWorldFactory demo.

function App() {
  const [locale, setLocale] = useState<"en" | "da" | null>(null);

  // Stable across re-renders: ScriptHostComponent tears down and rebuilds
  // the Pyodide worker whenever its bridge changes identity, which would
  // restart the whole flow mid-donation.
  const bridge = useMemo(() => new DownloadBridge(), []);

  if (locale === null) {
    return <LanguageSelect onSelect={setLocale} />;
  }

  return (
    <div className="App">
      <ScriptHostComponent
        workerUrl="./py_worker.js"
        locale={locale}
        // Explicit bridge rather than relying on the standalone/production
        // default. In a production build the default path is LiveBridge,
        // which waits for a `live-init` message from a hosting Next
        // platform — on a static deployment nothing ever answers and the
        // page sits blank forever. Verified: that is exactly what the
        // built app did before this was added.
        bridge={bridge}
        factories={[new DataSubmissionPageFactory({ promptFactories: [] })]}
        logLevel={import.meta.env.DEV ? "debug" : "info"}
      />
    </div>
  );
}

export default App;
