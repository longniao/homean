import { showingGuides } from "./showing-guides";
export type Resource = {
  slug: string; title: string; description: string; eyebrow: string;
  intro: string; sections: { title: string; text: string; bullets?: string[] }[];
  download?: string;
};
export const resourceCopy = {
  title: "Better notes. Clearer decisions.",
  description: "Free showing templates, practical guides, and a private browser tool for comparing homes. No account required.",
  eyebrow: "The showing notebook",
  read: "Open resource", print: "Print or save as PDF", download: "Download editable text",
  related: "Continue your showing notebook", home: "All resources", updated: "Updated September 10, 2026",
  nextTitle: "Keep the next conversation grounded in what you noticed.",
  nextText: "Homean is an early-beta workspace for buyer’s agents. Explore the report workflow and current availability before trying it.",
  nextLink: "How Homean works", worksheetTitle: "Compare your shortlist", worksheetNote: "Write on the printed worksheet. Keep filled copies private. A blank cell means unknown, not a positive finding.",
  criterion: "Question or priority", homeNumber: "Home", notes: "Your notes",
  worksheetRows: ["Property / visit date", "Our must-haves", "What stood out", "Trade-offs we can accept", "Concerns we noticed", "What each buyer thought", "Claims still unverified", "Questions for the agent", "Next step / owner"],
};
export const resources: Resource[] = [
  {
    slug: "showing-report-template", title: "Free real estate showing report template",
    description: "A printable showing report template for buyer’s agents: capture observations, buyer reactions, concerns, and follow-up questions. Includes an editable text download.",
    eyebrow: "01 / Field notes", download: "/downloads/showing-report-template.txt",
    intro: "Use this template after a home tour to preserve the details your buyer may need later. Start with their priorities, separate observations from claims, and finish with unanswered questions. Use it on its own or as a guide for an agent-reviewed Homean report.",
    sections: [
      { title: "1. Identify the visit", text: "Property: ____________________    Visit date and time: ____________________", bullets: ["Prepared by: ____________________", "Buyer priorities discussed for this visit: ____________________"] },
      { title: "2. Write a short recap", text: "In two or three sentences, describe the most relevant trade-offs for this buyer. Avoid repeating the listing description. If a priority was not assessed, say so.", bullets: ["What stood out: ____________________", "Main trade-off: ____________________", "Not assessed during this visit: ____________________"] },
      { title: "3. Separate what you know", text: "Use these four prompts to avoid turning an impression or someone else’s statement into an established fact.", bullets: ["Observed during our visit: ____________________", "Buyer reaction or preference: ____________________", "Reported by someone else — identify who: ____________________", "Not yet verified / evidence needed: ____________________"] },
      { title: "4. Keep room notes relevant", text: "For each useful space, record the room name, an observation, and the related photo or note reference. Leave out repetitive descriptions that do not help the buyer compare homes.", bullets: ["Space / observation / evidence reference: ____________________", "Concern or limitation of the observation: ____________________"] },
      { title: "5. Agree the next steps", text: "Turn uncertainty into a specific question rather than a confident conclusion.", bullets: ["Question: ____________________", "Who will follow up: ____________________", "When to revisit it: ____________________", "Agent review completed: ____________________"] },
      { title: "How to use this showing template", text: "Complete it while the visit is fresh, review it for accuracy, and share the relevant recap with your buyer. Bring it back when comparing the shortlist. This is a visit record, not a home inspection, valuation, or verification of a property’s condition." },
    ],
  },
  {
    slug: "sample-showing-report", title: "Example buyer’s agent showing report",
    description: "See a fictional showing report with a concise recap, buyer preferences, observed trade-offs, and questions to verify before the next step.",
    eyebrow: "02 / Worked example",
    intro: "Fictional example — 1840 Alder Lane. This is an editorial sample, not a real listing, inspection, customer record, or output from a completed AI trial. Every property detail and buyer preference below is invented to demonstrate the format.",
    sections: [
      { title: "The buyer’s priorities", text: "The household wants a quiet work space, room to cook together, and an entrance that is comfortable for a visiting parent who finds stairs difficult." },
      { title: "The short version", text: "The kitchen offered space for two people to cook, and the rear room may work as an office. Three entrance steps and audible street traffic are the main trade-offs to revisit. Renovation dates were reported by the listing representative and remain unverified." },
      { title: "What stood out", text: "Observations from this fictional afternoon visit:", bullets: ["The kitchen work surface had room for two people to stand side by side.", "The rear room was quieter than the front room while both doors were closed.", "The buyers liked the connection between the kitchen and dining space."] },
      { title: "Concerns and limits", text: "These notes describe one visit, not conditions at every time of day.", bullets: ["Three steps were present at the entrance. Accessibility changes were not assessed.", "Street traffic was audible in the front room during the visit.", "Morning light, roof condition, and heating performance were not assessed."] },
      { title: "Reported, not verified", text: "The listing representative stated that the kitchen was renovated in 2020. The buyers have not reviewed supporting documentation. The report should retain that attribution until evidence is available." },
      { title: "Questions and next steps", text: "For the next conversation with the agent:", bullets: ["Request any available renovation documentation and clarify what work it covers.", "Ask an appropriately qualified professional about entrance accessibility options before relying on a change being feasible.", "If quiet work space remains a priority, discuss whether another visit at a different time would help.", "Compare the entrance and office trade-offs with the household’s other shortlisted homes."] },
      { title: "What this report does not establish", text: "A showing recap does not establish structural safety, permitted use, renovation compliance, market value, or whether a home is right for a buyer. Agent review checks the report; professional assessments and supporting documents may still be needed." },
    ],
  },
  {
    slug: "home-comparison-worksheet", title: "Free home comparison tool and worksheet",
    description: "Compare two or three homes side by side. Enter priorities, trade-offs, and questions privately in your browser, then print or save your comparison as PDF.",
    eyebrow: "03 / The shortlist", download: "/downloads/home-comparison-worksheet.txt",
    intro: "After several tours, it is easy to confuse the quiet bedroom in one house with the generous kitchen in another. This free tool puts the same questions beside each home, so your household can discuss the differences without reducing the decision to a score.",
    sections: [
      { title: "Start with your own priorities", text: "Agree on a few must-haves before comparing the homes. Separate needs from preferences and allow household members to disagree. A large room is not automatically a benefit if your priority is a shorter commute or an easier entrance." },
      { title: "Compare like with like", text: "Use notes from each actual visit. Record the date and any relevant limits, such as only visiting in the afternoon. Write ‘not assessed’ when you do not have comparable information. Do not interpret a missing concern as evidence that a feature is problem-free." },
      { title: "Keep unknowns visible", text: "Put unverified renovation claims, unanswered questions, and documents still to review in their own row. Discuss who will obtain the information before treating it as a reason to proceed." },
      { title: "Use the worksheet with your agent", text: "Bring the worksheet to a shortlist conversation. Ask which uncertainty can be resolved and which trade-off is personal. A useful outcome may be ruling out a home, arranging another visit, or deciding you need more information." },
    ],
  },
  ...showingGuides,
];
