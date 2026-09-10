import { content } from "@/lib/content";

export function ProductComposition({ compact = false }: { compact?: boolean }) {
  const copy = content.productProof;
  return <div className={`dossier${compact ? " dossier-compact" : ""}`} aria-label={copy.compositionLabel}>
    <div className="dossier-topline"><span>{copy.sampleLabel}</span><span className="dossier-stamp">{copy.sampleCode}</span></div>
    <div className="report-preview">
      <div className="report-preview-title"><div><p className="eyebrow">{copy.reportLabel}</p><p className="report-title">{copy.reportTitle}</p></div>
        <svg className="report-emblem" viewBox="0 0 48 54" fill="none" aria-hidden="true"><path d="M5 24 24 7l19 17v24H5V24Z" stroke="currentColor" strokeWidth="1.5"/><path d="M18 48V30h12v18M12 24h5M31 24h5M24 7V2" stroke="currentColor" strokeWidth="1.5"/></svg>
      </div>
      <div className="report-observation"><p className="eyebrow">{copy.evidenceCategory}</p><p>{copy.evidenceText}</p></div>
      <span className="report-preview-status">{copy.evidenceState}</span>
    </div>
    <div className="report-source"><div className="report-source-label"><span>{copy.timelineLabel}</span><span>{copy.timelineTime}</span></div><blockquote>“{copy.timelineText}”</blockquote></div>
    <div className="dossier-footer"><span>{copy.reportFooter}</span><span>{copy.dossierPage}</span></div>
  </div>;
}
