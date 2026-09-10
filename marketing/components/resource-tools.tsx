"use client";
import { resourceCopy } from "@/lib/resources";
export function ResourceTools({ download }: { download?: string }) {
  return <div className="resource-actions no-print"><button className="button button-dark" data-measure="print_resource" onClick={() => window.print()}>{resourceCopy.print}</button>{download && <a className="text-link" href={download} download data-measure="download_resource">{resourceCopy.download} <span aria-hidden="true">↓</span></a>}</div>;
}
