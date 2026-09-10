export const comparisonCopy = {
  title: "Your shortlist, side by side",
  intro: "Add two or three homes and compare the same questions. Use a nickname instead of a full address if you prefer.",
  privacy: "Your entries stay in this page’s memory and are not sent to Homean. Entries are not saved; refreshing clears them, and leaving may also clear them. Print or save as PDF before leaving. We count comparison-button clicks, never your notes.",
  priorities: "Our shared priorities", prioritiesHint: "For example: a quiet workspace, an easy entrance, and room to cook together.",
  home: "Home", name: "Name or nickname", nameHint: "For example: Alder Lane", visit: "Visit date / time",
  compare: "Compare homes", edit: "Edit notes", print: "Print or save as PDF", clear: "Clear all notes",
  clearQuestion: "Clear these notes? This cannot be undone.", confirmClear: "Yes, clear notes", cancel: "Keep notes",
  minimum: "Name at least two homes to compare them.",
  previewTitle: "The shortlist conversation", question: "Question", unknown: "Not recorded — ask or assess",
  next: "Discuss the unknowns with your agent before treating a claim as a reason to proceed. This comparison does not verify a home’s condition or recommend a purchase.",
  fields: [
    { key: "highlights", label: "What stood out", hint: "What did you observe that relates to your priorities?" },
    { key: "tradeoffs", label: "Trade-offs and concerns", hint: "What may be difficult to live with? What did you not assess?" },
    { key: "reactions", label: "What each buyer thought", hint: "Keep different preferences visible; agreement is not required." },
    { key: "unknowns", label: "Claims still unverified", hint: "Who made the claim? What evidence would help?" },
    { key: "next", label: "Next question / owner", hint: "What needs checking, and who will follow up?" },
  ],
} as const;
export type HomeNotes = { name: string; visit: string; highlights: string; tradeoffs: string; reactions: string; unknowns: string; next: string };
export const emptyHomes = (): HomeNotes[] => Array.from({ length: 3 }, () => ({ name: "", visit: "", highlights: "", tradeoffs: "", reactions: "", unknowns: "", next: "" }));
