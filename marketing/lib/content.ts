export type WorkflowStep = {
  number: string;
  title: string;
  description: string;
  detail: string;
};

export type FaqItem = {
  question: string;
  answer: string;
};

export const content = {
  brandName: "Homean",
  metadata: {
    title: "AI Showing Reports & Home Comparisons for Buyer’s Agents | Homean",
    description: "Homean helps buyer’s agents turn a showing walkthrough into a private, reviewable client report.",
    socialDescription: "Capture a showing once. Review the structured draft. Deliver a report you stand behind.",
    socialAlt: "Homean showing records for buyer’s agents",
    twitterDescription: "A private showing record for buyer’s agents.",
  },
  nav: {
    howItWorks: "How it works",
    resources: "Free resources",
    forAgents: "For agents",
    trust: "Trust",
    signIn: "Sign in",
    signup: "Create account",
    mainNavigation: "Main navigation",
    homeLink: "Homean home",
    homeHref: "#main-content",
  },
  accessibility: { skipToMain: "Skip to main content" },
  hero: {
    eyebrow: "A showing record for buyer’s agents",
    title: "Every showing, clearly remembered.",
    description:
      "A considered record of every home. Turn showing notes into clear, private client reports—with your judgment at the center.",
    primaryCta: "Create account",
    secondaryCta: "Compare homes free",
    note: "Early beta · English only · Illustrative product view",
    sideNote: ["FIELD NOTE", "01—24"],
  },
  problem: {
    eyebrow: "The field note problem",
    title: "The showing ends. The real work begins.",
    description:
      "Photos in one place, voice notes in another, and the important detail you meant to write down somewhere in between. Homean keeps the showing record together while the visit is still fresh.",
    scatteredLabel: "Today’s scattered record",
    scatteredItems: ["Camera roll", "Voice memo", "Memory", "Follow-up text"],
    collectedLabel: "One private record",
    collectedItems: ["Capture", "Evidence", "Review", "Client report"],
    contrastLabel: "From scattered notes to one private record",
  },
  workflow: {
    eyebrow: "A calmer handoff",
    title: "From walkthrough to thoughtful follow-up.",
    description:
      "Homean fits around the way buyer’s agents already move through a home—then gives the record a clear shape.",
    steps: [
      {
        number: "01",
        title: "Capture naturally",
        description:
          "Use the mobile app to record your walkthrough, add photos, and speak as you go—even when connectivity is limited.",
        detail: "Mobile capture · offline-first",
      },
      {
        number: "02",
        title: "Review the draft",
        description:
          "The dashboard organizes the transcript into spaces and observations, with each detail connected back to its source.",
        detail: "Dashboard review · evidence linked",
      },
      {
        number: "03",
        title: "Confirm and deliver",
        description:
          "Edit what needs your voice, confirm the report, and send a private client version when it is ready.",
        detail: "Agent confirmed · private delivery",
      },
    ] satisfies WorkflowStep[],
  },
  productProof: {
    eyebrow: "Inside a showing record",
    title: "Every detail has a source.",
    description:
      "The sample below is fictional and illustrative. It shows the relationship between a timed capture, an observation, and a polished report—not a customer record.",
    sampleLabel: "Fictional sample · 1840 Alder Lane",
    timelineLabel: "Walkthrough timeline",
    timelineTime: "10:42:18",
    timelineText: "Kitchen has a generous south-facing window; counters look recently replaced.",
    evidenceLabel: "Evidence-linked observation",
    evidenceCategory: "LIGHT · KITCHEN",
    evidenceText: "South-facing window brings strong natural light into the kitchen.",
    evidenceState: "Pending agent review",
    reportLabel: "Client report",
    reportTitle: "Showing notes",
    reportText:
      "A bright kitchen with a generous work surface and a recently updated feel.",
    reportFooter: "Private · ready after confirmation",
    sampleCode: "SAMPLE / 001",
    captureSource: "VOICE NOTE",
    captureStatus: "SYNCED",
    dossierFooter: "AI ORGANIZED · AGENT REVIEW REQUIRED",
    dossierPage: "03 / 03",
    compositionLabel: "Illustrative showing record",
  },
  agents: {
    eyebrow: "Built for the buyer’s side",
    title: "Your expertise. A clearer record.",
    description:
      "Homean is for active buyer’s agents who want to turn field observations into a clearer client experience—without asking AI to make the decision for them.",
    points: [
      {
        title: "Keep the whole visit together",
        description: "Voice, photos, transcript, and observations stay connected to one showing record.",
      },
      {
        title: "Make review part of the workflow",
        description: "AI creates a draft. You edit, confirm, and decide what is ready to share.",
      },
      {
        title: "Give clients something considered",
        description: "A structured report makes the next conversation easier to start and easier to remember.",
      },
    ],
    signupLink: "Create your account",
  },
  trust: {
    eyebrow: "Product principles",
    title: "Built around your judgment.",
    description:
      "Homean is designed around a simple boundary: organize the record, keep the judgment with the professional.",
    principles: [
      { label: "Private by default", description: "Showing records are private unless you choose to deliver one to a client." },
      { label: "Agent-reviewed before delivery", description: "AI output is a draft. Nothing is delivered without your explicit confirmation." },
      { label: "Evidence stays connected", description: "Observations can remain linked to transcript moments and original media." },
      { label: "Made for the field", description: "Offline-first capture protects the workflow when a showing has a weak signal." },
    ],
  },
  signup: {
    eyebrow: "Ready for the next showing",
    title: "Explore a clearer showing workflow.",
    description:
      "Explore the beta dashboard and fictional examples. AI processing and mobile capture are still being validated before general availability.",
    cta: "Create your account",
    note: "Account creation continues securely in the Homean dashboard.",
  },
  faq: {
    eyebrow: "Questions agents ask",
    title: "A few useful answers before you start.",
    items: [
      {
        question: "Who is Homean for?",
        answer: "Homean is being built for active buyer’s agents who want a more consistent way to capture, review, and deliver private showing notes to their clients.",
      },
      {
        question: "Does Homean send AI output automatically?",
        answer: "No. AI output starts as a draft. You review and explicitly confirm a report before it can be delivered.",
      },
      {
        question: "Are reports public?",
        answer: "No. Reports are private by default and intended for the agent and the client the agent chooses to share with.",
      },
      {
        question: "What happens without connectivity?",
        answer: "The mobile capture workflow is designed for offline-first use. Captured media can remain on the device and sync when connectivity returns.",
      },
      {
        question: "How do I get started?",
        answer: "Create an account in the Homean dashboard. Once signed in, you can start organizing showing records and client reports.",
      },
    ] satisfies FaqItem[],
  },
  footer: {
    line: "A private showing record for buyer’s agents.",
    availability: "Early beta · English only",
    privacy: "Private by default. Agent-reviewed before delivery.",
    copyright: "© 2026 Homean.",
    signature: "Built for the field.",
  },
} as const;
