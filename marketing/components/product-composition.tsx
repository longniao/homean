import { content } from "@/lib/content";

type ProductCompositionProps = {
  compact?: boolean;
};

export function ProductComposition({ compact = false }: ProductCompositionProps) {
  return (
    <div
      className={`dossier${compact ? " dossier-compact" : ""}`}
      aria-label={content.productProof.compositionLabel}
    >
      <div className="dossier-topline">
        <span>{content.productProof.sampleLabel}</span>
        <span className="dossier-stamp">{content.productProof.sampleCode}</span>
      </div>
      <div className="composition-grid">
        <div className="capture-panel composition-panel">
          <div className="panel-kicker"><span className="record-dot" />{content.productProof.timelineLabel}</div>
          <div className="timeline-track" aria-hidden="true">
            <span className="timeline-line" />
            <span className="timeline-point point-one" />
            <span className="timeline-point point-two" />
            <span className="timeline-point point-three active" />
            <span className="timeline-point point-four" />
          </div>
          <div className="capture-time">{content.productProof.timelineTime} <span>· 00:38</span></div>
          <p className="capture-quote">“{content.productProof.timelineText}”</p>
          <div className="capture-meta"><span>{content.productProof.captureSource}</span><span>{content.productProof.captureStatus}</span></div>
        </div>
        <div className="evidence-panel composition-panel">
          <div className="evidence-tab">{content.productProof.evidenceLabel}</div>
          <div className="evidence-bracket" aria-hidden="true"><span /></div>
          <p className="evidence-category">{content.productProof.evidenceCategory}</p>
          <p className="evidence-copy">{content.productProof.evidenceText}</p>
          <div className="review-row"><span className="review-ring" />{content.productProof.evidenceState}</div>
        </div>
        <div className="report-panel composition-panel">
          <div className="report-paperclip" aria-hidden="true" />
          <div className="panel-kicker">{content.productProof.reportLabel}</div>
          <div className="report-rule" />
          <p className="report-title">{content.productProof.reportTitle}</p>
          <p className="report-copy">{content.productProof.reportText}</p>
          <div className="report-photo" aria-hidden="true"><span className="window-shape" /><span className="plant-shape" /></div>
          <div className="report-footer">{content.productProof.reportFooter}</div>
        </div>
      </div>
      <div className="dossier-footer"><span>{content.productProof.dossierFooter}</span><span>{content.productProof.dossierPage}</span></div>
    </div>
  );
}
