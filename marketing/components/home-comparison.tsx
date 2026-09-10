"use client";
import { useEffect, useRef, useState } from "react";
import { comparisonCopy as copy, emptyHomes, type HomeNotes } from "@/lib/comparison";

export function HomeComparison() {
  const [homes, setHomes] = useState(emptyHomes);
  const [priorities, setPriorities] = useState("");
  const [preview, setPreview] = useState(false);
  const [clearing, setClearing] = useState(false);
  const resultHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { if (preview) resultHeading.current?.focus(); }, [preview]);
  const named = homes.filter(home => home.name.trim());
  const populated = homes.flatMap((home, index) => Object.values(home).some(value => value.trim())
    ? [{ ...home, name: home.name.trim() || `${copy.home} ${index + 1}` }] : []);
  const displayed = populated.length ? populated : homes;
  const update = (index: number, key: keyof HomeNotes, value: string) => {
    setHomes(current => current.map((home, i) => i === index ? { ...home, [key]: value } : home));
  };
  const rows = [{ key: "visit" as const, label: copy.visit }, ...copy.fields];
  return <section className="comparison-tool" aria-labelledby="comparison-title">
    <div className="no-print"><p className="eyebrow">{copy.home} / 01—03</p><h2 id="comparison-title">{copy.title}</h2><p>{copy.intro}</p><p className="comparison-privacy">{copy.privacy}</p></div>
    <div className={`comparison-editor no-print${preview ? " comparison-hidden" : ""}`}>
      <label className="comparison-priorities">{copy.priorities}<textarea rows={2} maxLength={2000} value={priorities} onChange={event => setPriorities(event.target.value)} placeholder={copy.prioritiesHint} /></label>
      <div className="comparison-cards">{homes.map((home, index) => <fieldset key={index} className="comparison-card"><legend>{copy.home} {index + 1}</legend>
        <label>{copy.name}<input maxLength={120} value={home.name} placeholder={copy.nameHint} onChange={event => update(index, "name", event.target.value)} /></label>
        <label>{copy.visit}<input maxLength={120} value={home.visit} onChange={event => update(index, "visit", event.target.value)} /></label>
        {copy.fields.map(field => <label key={field.key}>{field.label}<textarea rows={3} maxLength={2000} value={home[field.key]} placeholder={field.hint} onChange={event => update(index, field.key, event.target.value)} /></label>)}
      </fieldset>)}</div>
      <p id="comparison-minimum">{copy.minimum}</p>
      <button className="button button-dark" disabled={named.length < 2} aria-describedby="comparison-minimum" data-measure="comparison_view" onClick={() => setPreview(true)}>{copy.compare} →</button>
    </div>
    <div className={`comparison-result${preview ? "" : " comparison-print-only"}`}>
      <h2 ref={resultHeading} tabIndex={-1}>{copy.previewTitle}</h2><h3>{copy.priorities}</h3><p className="comparison-note">{priorities.trim() || copy.unknown}</p>
      <div className="comparison-table-scroll"><table><thead><tr><th scope="col">{copy.question}</th>{displayed.map((home, index) => <th scope="col" key={index}>{home.name || `${copy.home} ${index + 1}`}</th>)}</tr></thead><tbody>{rows.map(row => <tr key={row.key}><th scope="row">{row.label}</th>{displayed.map((home, index) => <td key={index}>{home[row.key].trim() || copy.unknown}</td>)}</tr>)}</tbody></table></div>
      <p className="comparison-caution">{copy.next}</p>
      <div className="resource-actions no-print"><button className="button button-dark" data-measure="print_comparison" onClick={() => window.print()}>{copy.print}</button><button className="text-link" onClick={() => setPreview(false)}>{copy.edit}</button></div>
    </div>
    <div className="comparison-reset no-print">{clearing ? <><p>{copy.clearQuestion}</p><button className="text-link" onClick={() => { setHomes(emptyHomes()); setPriorities(""); setPreview(false); setClearing(false); }}>{copy.confirmClear}</button><button className="text-link" onClick={() => setClearing(false)}>{copy.cancel}</button></> : <button className="text-link" onClick={() => setClearing(true)}>{copy.clear}</button>}</div>
  </section>;
}
