import { postFile } from "@/lib/api";

/** One set of file rules for every upload button, so each one says the same helpful thing about the same problem. */
export type FileKind = "data" | "text" | "anything" | "csv" | "pcap" | "backup";

const EXT = {
  img: ["png", "jpg", "jpeg", "tif", "tiff", "bmp", "webp"],
  table: ["csv", "tsv", "txt", "log", "dat", "xlsx", "xlsm", "json", "jsonl", "ndjson", "xml", "pdf", "parquet", "html", "htm"],
  doc: ["xlsx", "xlsm", "pdf", "docx"],
  text: ["txt", "md", "log", "csv", "tsv", "json"],
};
const ALLOWED: Record<FileKind, string[]> = {
  data: EXT.table,
  text: [...EXT.text, ...EXT.doc, ...EXT.img],
  anything: [...EXT.text, ...EXT.doc, ...EXT.img, "evtx"],
  csv: ["csv"],
  pcap: ["pcap", "pcapng", "cap"],
  backup: ["duckdb"],
};
const WHAT: Record<FileKind, string> = {
  data: "CSV, TSV, Excel (.xlsx), JSON, XML, PDF with a table, Parquet or HTML",
  text: "text, CSV, log, JSON, Excel, PDF, Word or a picture of a document",
  anything: "Excel, PDF, Word, a picture of a document (png or jpg), csv, tsv, txt, log, json or md",
  csv: "CSV",
  pcap: ".pcap, .pcapng or .cap capture",
  backup: ".duckdb backup",
};
const MAX_MB: Partial<Record<FileKind, number>> = { text: 25, anything: 25, pcap: 6 };
const PARTIAL = /\.(crdownload|part|partial|download|opdownload|tmp|temp)$/i;
const ext = (n: string) => /\.([a-z0-9]+)$/i.exec(n)?.[1].toLowerCase() ?? "";

export const acceptFor = (k: FileKind) => ALLOWED[k].map((e) => `.${e}`).join(",");

/** Returns a plain-English problem with the file, or null when it looks fine. Checks the name and size only; the server still reads it properly. */
export function checkFile(f: File, kind: FileKind): string | null {
  if (PARTIAL.test(f.name)) {
    const done = f.name.replace(PARTIAL, "");
    return `"${f.name}" is a download that hasn't finished (the browser adds that ending until it is done). Wait for the download to complete, then pick "${done}" from your Downloads folder.`;
  }
  if (f.size === 0) return `"${f.name}" is empty (0 bytes). Download or export it again.`;
  const e = ext(f.name);
  if (e === "xls") return "This is an old Excel (.xls) file. Open it in Excel and use Save As, then choose Excel Workbook (.xlsx) or CSV.";
  if (e === "evtx" && kind !== "anything") return "An .evtx file is binary. In Event Viewer choose Action, Save All Events As, and pick CSV, then upload that.";
  if (kind === "anything" && e === "evtx") return "An .evtx file is binary. In Event Viewer choose Action, Save All Events As, and pick CSV, then upload that.";
  if (!ALLOWED[kind].includes(e)) {
    const hint = ["zip", "7z", "rar", "gz"].includes(e) ? " Unzip it first and pick the file inside." : ["doc", "ppt", "pptx", "rtf", "odt"].includes(e) ? " Save it as PDF or Word (.docx) first." : "";
    return `This button reads ${WHAT[kind]} files, and "${f.name}" is ${e ? `a .${e}` : "a file with no ending"}.${hint}`;
  }
  const max = MAX_MB[kind];
  if (max && f.size > max * 1024 * 1024) return `That file is over ${max} MB. Export a smaller slice.`;
  return null;
}

/** For readers that only take plain text: turns an Excel, PDF or Word file into a text file first (done by your own backend, nothing is stored). Other files pass through unchanged. */
export async function readableFile(f: File): Promise<File> {
  if (!/\.(xlsx|xlsm|pdf|docx|png|jpe?g|tiff?|bmp|webp)$/i.test(f.name)) return f;
  const r = await postFile<{ text: string }>("/api/files/text", f);
  return new File([r.text], f.name.replace(/\.[^.]+$/, "") + ".txt", { type: "text/plain" });
}
