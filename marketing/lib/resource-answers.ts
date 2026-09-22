export const editorialCopy = {
  breadcrumb: "Breadcrumb",
  home: "Home",
  resources: "Free resources",
  by: "By",
  updated: "Updated",
  contents: "On this page",
  answersTitle: "Useful answers",
  formatTitle: "About this resource",
  formatText: "Prepared by Homean as an AI-assisted editorial resource. Examples are fictional teaching material, not customer reports or independently verified property findings.",
  policyLink: "Our editorial approach",
  sourceTitle: "Further reading",
  sourceContext: "For the distinction between an inspection and an appraisal, see this U.S. consumer resource. It does not validate the fictional properties or provide rules for other jurisdictions.",
  sourceLabel: "CFPB: Schedule a home inspection",
  sourceUrl: "https://www.consumerfinance.gov/owning-a-home/close/schedule-a-home-inspection/",
  next: "Put this into practice",
};

type ResourceAnswers = {
  question: string;
  answer: string;
  questions: { question: string; answer: string }[];
  nextSlug: string;
  nextLabel: string;
  inspectionSource?: boolean;
};

export const resourceAnswers: Record<string, ResourceAnswers> = {
  "showing-report-template": {
    question: "What should a buyer’s agent showing report include?",
    answer: "Include the property and visit date, buyer priorities, a short recap, room observations, buyer reactions, attributed claims, and open questions with a follow-up owner. Preserve uncertainty and review the report before sharing. The template below is free to print or download as editable text, without an account.",
    questions: [
      { question: "Is a showing report the same as seller feedback?", answer: "In this template, a showing report is a private recap for the buyer: what they noticed, what mattered to them, and what needs checking. Seller feedback has a different audience. Do not copy a buyer’s private concerns or negotiating intentions into feedback for a seller without discussing what should be shared." },
      { question: "Can I edit this template in Word or Google Docs?", answer: "Yes. Download the editable text file, then open or paste its contents into your document editor. The download is plain text, not a preformatted Word document. You can also use Print or save as PDF on this page." },
      { question: "Does a completed showing report replace an inspection?", answer: "No. A showing report preserves visit notes and buyer reactions. It does not independently assess building systems, diagnose defects, establish market value, or replace a professional inspection or appraisal." },
    ],
    nextSlug: "sample-showing-report", nextLabel: "See a complete fictional showing report",
    inspectionSource: true,
  },
  "sample-showing-report": {
    question: "What does a useful showing report look like?",
    answer: "A useful showing report begins with the buyer’s priorities and a short recap, then separates observations, reactions, reported claims, and unanswered questions. The fictional example below shows how to keep visit conditions and uncertainty visible while giving each important question a next step.",
    questions: [
      { question: "Was this sample generated from an actual showing?", answer: "No. The address, buyer priorities and observations are invented to demonstrate the format. This is an editorial example, not a customer testimonial, a real listing, or evidence that Homean’s live AI pipeline has been validated." },
      { question: "How should I describe something the listing agent told me?", answer: "Name the source and retain its verification status. For example: ‘The listing representative reported a 2020 renovation; supporting records have not been reviewed.’ Do not silently rewrite that as a confirmed renovation date." },
      { question: "What if a feature was not checked during the tour?", answer: "Write ‘not assessed’ and, if the feature matters to the buyer, add a follow-up question. An empty note or lack of visible damage does not establish that a feature is problem-free." },
    ],
    nextSlug: "showing-report-template", nextLabel: "Download the blank showing report template",
  },
  "home-comparison-worksheet": {
    question: "How can I compare two or three homes side by side?",
    answer: "Use the same questions for each home: buyer priorities, visit observations, trade-offs, concerns, unverified claims and next steps. Enter them in the free comparison tool below, or start with its fictional example. No account is needed; print or save a PDF before leaving because notes are not saved after a refresh.",
    questions: [
      { question: "Are my comparison notes uploaded or saved?", answer: "The public comparison tool keeps entries in the current page’s memory. Homean does not upload or save those notes through this tool. Refreshing or closing the page clears them. Save a PDF if you want to keep a copy, and keep that file private. Aggregate page and button counts do not contain your notes." },
      { question: "Can I compare homes without assigning scores?", answer: "Yes. This tool shows your notes side by side without ranking properties or declaring a winner. The purpose is to make personal trade-offs and unanswered questions easier to discuss with your household and agent." },
      { question: "What should I do when one home has missing information?", answer: "Leave it marked as unknown or write ‘not assessed.’ Add a question and an owner for follow-up. Do not treat missing information as a positive finding, and record visit conditions when the homes were observed at different times." },
    ],
    nextSlug: "how-to-compare-homes-after-touring", nextLabel: "Read the step-by-step home comparison guide",
  },
  "how-to-compare-homes-after-touring": {
    question: "What is a practical way to compare homes after touring?",
    answer: "Start with shared priorities, reconstruct each visit separately, and compare the same observations across the shortlist. Keep buyer preferences apart from property claims. Record unknowns and decide who will follow up; a second visit or more information may be a better next step than forcing a decision.",
    questions: [
      { question: "How do I compare visits made at different times of day?", answer: "Write down the time and conditions for each observation. A quiet Sunday visit and a weekday rush-hour visit are not equivalent evidence about traffic noise. If the difference affects a priority, ask whether another visit would help rather than assuming the homes were assessed equally." },
      { question: "What if household members prefer different homes?", answer: "Record each person’s reaction separately before discussing shared requirements. Identify the exact trade-off behind the preference, such as a separate workspace versus a larger kitchen. The worksheet helps preserve those differences; it does not decide whose preference should win." },
      { question: "Can showing notes tell me which home is structurally sound?", answer: "No. Visit notes record what was noticed under limited conditions. They do not establish structural condition. Keep inspection findings and valuation information distinct from your tour impressions, and discuss the appropriate assessments with your agent and qualified professionals." },
    ],
    nextSlug: "home-comparison-worksheet", nextLabel: "Compare your shortlist with the free tool",
    inspectionSource: true,
  },
  "what-to-write-after-a-showing": {
    question: "What should I write to a buyer after a showing?",
    answer: "Write a short recap of the buyer’s priorities, the most relevant observations, their reactions, the main trade-off and the next unanswered question. Attribute information from other people and preserve uncertainty. Add who will follow up, then review the wording before sending it to the intended buyer.",
    questions: [
      { question: "How long should a showing recap be?", answer: "Homean’s suggested format starts with two or three sentences, followed by only the room notes and follow-up questions that help this buyer. This is an editorial starting point, not an industry rule. Add detail when the visit or the buyer’s priorities require it." },
      { question: "Can I send an AI-written recap without reviewing it?", answer: "Homean’s report workflow requires explicit agent confirmation before delivery. Review whether the wording matches the underlying notes, retains uncertainty and names the source of reported claims. A polished sentence is not evidence that its assertion is correct." },
      { question: "How do I turn ‘possible water mark’ into a useful follow-up?", answer: "Keep the uncertainty: ‘A possible mark was noticed below the window; its cause has not been established.’ Then name the question and owner, such as asking the agent what information is available. Do not rewrite the note as a confirmed leak or a diagnosis." },
    ],
    nextSlug: "showing-report-template", nextLabel: "Use the free showing report template",
  },
};
