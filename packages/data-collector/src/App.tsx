import { useState } from "react";
import { DataSubmissionPageFactory, ScriptHostComponent } from "@eyra/feldspar";
import { LanguageSelect } from "./components/language_select/component";

// Every PropsUI* type script.py actually uses (radio input, file
// input, confirm, text, consent table, submission buttons) is covered
// by Feldspar's own default prompt factories — no custom factory
// needed here, unlike upstream's HelloWorldFactory demo.

function App() {
  const [locale, setLocale] = useState<"en" | "da" | null>(null);

  if (locale === null) {
    return <LanguageSelect onSelect={setLocale} />;
  }

  return (
    <div className="App">
      <ScriptHostComponent
        workerUrl="./py_worker.js"
        locale={locale}
        standalone={import.meta.env.DEV}
        factories={[new DataSubmissionPageFactory({ promptFactories: [] })]}
        logLevel={import.meta.env.DEV ? "debug" : "info"}
      />
    </div>
  );
}

export default App;
