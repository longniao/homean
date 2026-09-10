import type { Resource } from "./resources";
export const showingGuides: Resource[] = [
  {
    slug: "how-to-compare-homes-after-touring", title: "How to compare homes after touring",
    description: "A practical way to compare two or three homes: agree on priorities, separate observations from impressions, keep unknowns visible, and plan the next conversation.",
    eyebrow: "04 / Buyer guide",
    intro: "Compare homes using the same buyer priorities and the notes from each visit. Separate what you observed, what each person preferred, and what still needs checking. Finish with a next step for each unresolved question, rather than choosing a winner from a total score.",
    sections: [
      { title: "1. Agree on the questions before comparing answers", text: "Write down a few shared priorities before discussing your favourite home. Turn vague preferences into questions you can revisit. ‘A good office’ might mean a room with a door, acceptable noise during working hours, and space for your desk. Keep a preference separate from a requirement.", bullets: ["Which needs would make a home unsuitable if they were not met?", "Which preferences could you trade for something else?", "Where do members of the household disagree?"] },
      { title: "2. Reconstruct each visit separately", text: "Give every home a name and visit date. Review your own notes and permitted photos before discussing the shortlist. Record conditions that limit the comparison: a short afternoon visit does not establish morning light or evening traffic. Leave an answer marked ‘not assessed’ when you did not check it." },
      { title: "3. Separate observations, reactions, and claims", text: "‘We heard traffic in the front room’ is an observation from a particular visit. ‘I would find that distracting’ is a buyer reaction. ‘The windows were replaced recently’ is a claim that needs attribution and, if it matters to the decision, supporting information. Keeping these apart makes the comparison more useful." },
      { title: "4. Make trade-offs explicit", text: "Fictional example: Alder Lane had a larger kitchen but three entrance steps. Cedar Place had a smaller kitchen and a step-free entrance during the visit. If an easier entrance matters to your household, the kitchen difference alone should not settle the discussion. Neither visit establishes whether future alterations would be feasible." },
      { title: "5. Turn unknowns into next steps", text: "Write a question and an owner beside each important unknown. ‘Ask the agent what renovation records are available’ is more actionable than ‘check renovations.’ Your next step might be a second visit, requesting documentation, consulting an appropriate professional, or deciding the trade-off does not fit your needs." },
      { title: "Use the free comparison tool", text: "Open the home comparison worksheet below to enter two or three homes, put your notes beside each other, and print the result. Entries stay in the page’s memory; save a PDF before leaving. The tool does not establish condition, affordability, market value, or which home you should buy." },
    ],
  },
  {
    slug: "what-to-write-after-a-showing", title: "What to write after a real estate showing",
    description: "A buyer’s agent guide to writing a useful showing recap: priorities, observations, buyer reactions, unverified claims, and follow-up questions, with a fictional example.",
    eyebrow: "05 / Agent guide",
    intro: "A useful showing recap records what mattered to this buyer: the relevant observations, their reactions, the main trade-offs, and questions still open. Keep it concise enough to revisit when comparing homes. Attribute claims instead of turning them into facts.",
    sections: [
      { title: "Start with the buyer’s priorities", text: "Record the property and visit date, then name the priorities that shaped the visit. For example, a quiet place to work and an easier entrance are more useful context than a generic list of room features. If a priority changed during the conversation, make that clear." },
      { title: "Write a short recap before the room notes", text: "Use a few sentences to explain the most relevant benefit, trade-off, and unknown. Detailed room notes can support the recap, but the buyer should not have to read every observation to find the next question." },
      { title: "A fictional recap you can adapt", text: "‘The rear room felt quieter than the front room during our afternoon visit, and you liked its separation from the kitchen. The three entrance steps remain a concern for visiting family. The listing representative reported a 2020 kitchen renovation; we have not reviewed documentation. Next: request the available records and discuss whether another visit would help assess the workspace.’ This is an invented teaching example, not a report about a real property." },
      { title: "Keep four kinds of information distinct", text: "A polished report should preserve the limits of the underlying notes.", bullets: ["Observed: what you saw or heard, with relevant visit conditions.", "Buyer reaction: what the buyer expressed, including disagreement.", "Reported claim: what someone else said, with the source identified.", "Unknown: what was not assessed or what evidence is still needed."] },
      { title: "Make follow-up easy to act on", text: "For each open question, record who will follow up and when to revisit it. Prioritize the questions that affect the buyer’s next step. A recap can end with ‘more information needed’; it does not need to sound conclusive." },
      { title: "Review the recap before sharing", text: "Check that the recap accurately represents the notes and buyer reactions. Remove unsupported conclusions, distinguish someone else’s statement from your observation, and confirm the intended recipients. An agent’s review does not independently verify property condition or replace professional assessments." },
      { title: "Use a template without making every report identical", text: "The free showing report template below provides prompts for these sections. Leave out repetitive descriptions that do not help this buyer. Homean’s early-beta dashboard supports report review and comparisons; general AI processing and mobile capture availability remain limited as described on the How it works page." },
    ],
  },
];
