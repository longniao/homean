export const comparisonCopy = {
  privacyTitle: "Private entries · Notes are not saved",
  title: "Your shortlist, side by side",
  intro: "Add two or three homes and compare the same questions. Use a nickname instead of a full address if you prefer.",
  privacy: "Your entries stay in this page’s memory and are not sent to Homean. Entries are not saved; refreshing clears them, and leaving may also clear them. Print or save as PDF before leaving. We count comparison-button clicks, never your notes.",
  priorities: "Our shared priorities", prioritiesHint: "For example: a quiet workspace, an easy entrance, and room to cook together.",
  home: "Home", name: "Name or nickname", nameHint: "For example: Alder Lane", visit: "Visit date / time",
  compare: "Compare homes", edit: "Edit notes", print: "Print or save as PDF", clear: "Clear all notes",
  clearQuestion: "Clear these notes? This cannot be undone.", confirmClear: "Yes, clear notes", cancel: "Keep notes",
  minimum: "Name at least two homes to compare them.",
  exampleAction: "See a filled example",
  exampleHelp: "Explore three fictional homes. Your own notes stay untouched.",
  exampleLabel: "Fictional example — not real listings or a customer report",
  exampleReturn: "Back to my notes",
  examplePrint: "Print example",
  tableHint: "Swipe sideways to see every home.",
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

export const comparisonExample = {
  priorities: "A quiet place to work, space to cook together, and an entrance comfortable for a visiting parent who finds stairs difficult.",
  homes: [
    {
      name: "Alder Lane (fictional)", visit: "Saturday, 2:00 p.m.",
      highlights: "Two people could stand side by side at the kitchen counter. The rear room was quieter than the front room with doors closed.",
      tradeoffs: "Three steps at the entrance. Street traffic audible in the front room during this visit.",
      reactions: "Alex liked the kitchen. Sam wanted to revisit the entrance before shortlisting.",
      unknowns: "The listing representative said the kitchen was renovated in 2020; supporting documents have not been reviewed.",
      next: "Agent: request available renovation documents. Household: discuss how often step-free access is needed.",
    },
    {
      name: "Cedar Court (fictional)", visit: "Saturday, 3:00 p.m.",
      highlights: "No steps on the entrance route used during the visit. A separate room could be considered for a workspace.",
      tradeoffs: "The kitchen felt tight with two people beside the counter. Noise at workday hours was not assessed.",
      reactions: "Sam preferred the entrance. Alex wanted to check whether their kitchen routine would fit.",
      unknowns: "The entrance was observed on one route only; suitability for the visiting parent has not been assessed.",
      next: "Household: review the kitchen layout. Agent: ask whether another visit at workday hours can be arranged.",
    },
    {
      name: "Birch Place (fictional)", visit: "Sunday, 11:00 a.m.",
      highlights: "Space beside the dining area might fit a desk. Both buyers liked the connection to the kitchen.",
      tradeoffs: "The possible desk area has no separating door. One step on the entrance route used.",
      reactions: "Alex liked the open layout. Sam was concerned about calls while someone else cooks.",
      unknowns: "Furniture fit and weekday noise are unassessed. The buyers have not checked their desk measurements.",
      next: "Household: measure the desk and agree whether a separate workspace is a must-have.",
    },
  ] satisfies HomeNotes[],
};
