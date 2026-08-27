import type { Bridge } from "@eyra/feldspar";

/**
 * A donation sink for the standalone public demo.
 *
 * There is no research backend here and there should not be one: a
 * public demo that quietly accepted real people's media histories onto
 * a server would be the exact opposite of the privacy story this
 * project is making. So "donating" hands the JSON back to the person
 * who produced it, as a file download, and nothing leaves their
 * machine at any point.
 *
 * In a real study this is where a Next platform submission (LiveBridge)
 * or an institution's own endpoint would go — see MONITORING.md and the
 * README for what a real deployment would need to add.
 */
export class DownloadBridge {
  send(command: any): void {
    if (command?.__type__ === "CommandSystemDonate") {
      this.download(command.key, command.json_string);
    } else if (command?.__type__ === "CommandSystemExit") {
      console.log(`[DownloadBridge] flow finished: ${command.code} ${command.info}`);
    }
  }

  /** Logs are kept in the console only — nothing is transmitted anywhere. */
  sendLogs(entries: { level: string; message: string }[]): void {
    entries.forEach((e) => console.log(`[DownloadBridge] ${e.level}: ${e.message}`));
  }

  private download(key: string, jsonString: string): void {
    // Pretty-print when possible: the point of handing the file back is
    // that a participant (or a reviewer) can actually open it and read
    // what they would have shared.
    let body = jsonString;
    try {
      body = JSON.stringify(JSON.parse(jsonString), null, 2);
    } catch {
      // A declined donation is a bare JSON string rather than an object;
      // hand it over as-is rather than failing the download.
    }

    const blob = new Blob([body], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${key || "donation"}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    // Revoked on a delay: revoking synchronously can cancel the download
    // in some browsers before it has started reading the blob.
    setTimeout(() => URL.revokeObjectURL(url), 10_000);
  }
}

// Structural check that this still satisfies Feldspar's Bridge contract.
// If the interface gains a method, this line fails at build time rather
// than the demo failing silently at donate time in front of a visitor.
const _contractCheck: Bridge = new DownloadBridge();
void _contractCheck;
