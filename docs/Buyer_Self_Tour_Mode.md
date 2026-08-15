# Buyer Self-Tour Mode — Product Concept

## Background

The original workflow assumes:

> Realtor attends the showing → captures photos / voice notes → AI generates a buyer-ready Home Tour Report.

There is another important real-world scenario:

> The Realtor does not attend the showing. The buyer receives access instructions / door code and tours the property independently.

The buyer should therefore be able to use the product directly.

This should use the same underlying architecture:

> **Home → Tour → Capture → AI → Summary → Compare → Share**

## Core Buyer Problem

After viewing 5–20 properties, buyers often forget which home had which kitchen, basement concern, old roof, backyard, traffic noise, question, or family reaction. Their camera roll becomes a collection of photos with little context.

The product should solve:

> **I've seen many homes. Help me remember exactly what I saw, compare them, and decide what to do next.**

## Buyer Value Proposition

Primary positioning:

> **Remember every home you tour.**

Alternative:

> **Tour homes. Capture what matters. Compare with confidence.**

The buyer should not feel that they are writing a report. The product should feel like:

> **AI memory for your home search.**

## Core User Flow

### 1. Start Tour

Buyer arrives at a property and taps **Start Tour**.

Create a Tour associated with the property. Where possible, prefill address, listing price, bedrooms, bathrooms, listing URL, and basic property information.

Do not require a long form before entering the home.

### 2. Capture During Tour

Mobile-first inputs:

- photo
- video
- voice note
- text note
- rating / reaction
- room/context
- timestamp

Example:

> “Kitchen looks recently renovated. We both really like this one.”

> “There’s a damp smell here. Ask the Realtor about previous water damage.”

> “Smaller than yesterday’s backyard, but much more private.”

The buyer should not manually organize these notes.

### 3. Finish Tour

Tap **Finish Tour**.

AI organizes captured material into a structured Tour Summary.

## AI Understanding

Transform raw input into structured observations:

### Likes
- renovated kitchen
- private backyard
- good natural light

### Concerns
- possible basement moisture
- roof appears old
- traffic noise

### Questions
- When was the roof replaced?
- Any previous water ingress?
- Were basement renovations permitted?

### Buyer Reactions
- buyer strongly liked kitchen
- spouse disliked bedroom size
- backyard was a major positive

### Property Characteristics
- layout
- condition
- room sizes
- storage
- parking
- neighborhood impression
- renovation quality

Preserve the original photo / voice note linked to each AI-generated observation.

## Tour Summary

Example:

### 19741 47 Avenue

**Likes**
- renovated kitchen
- private backyard
- large garage

**Concerns**
- damp smell in basement
- roof may need replacement

**Questions for Realtor**
1. Has there been previous basement water damage?
2. When was the roof last replaced?
3. Are permits available for the basement renovation?

**Overall Impression**

> Strong candidate. Kitchen and privacy were major positives, but basement moisture should be investigated.

The user must be able to edit AI-generated information.

## Compare Multiple Homes

After multiple tours, provide **Compare Homes**.

| Attribute | Home A | Home B | Home C |
|---|---|---|---|
| Kitchen | ❤️ | 😐 | ❤️ |
| Backyard | ❤️ | ❤️ | 😐 |
| Basement | ⚠️ | ✅ | ✅ |
| Noise | ✅ | ⚠️ | ✅ |
| Price | $999K | $1.05M | $1.02M |
| Buyer Rating | 8.7 | 7.9 | 8.5 |

Support questions such as:

- Which home did we like most?
- Which homes had basement concerns?
- Which property had the best backyard?
- Show me all unanswered questions.
- Which home best matches our priorities?

Clearly distinguish buyer observations, listing information, AI inference, and verified facts.

## Share With Realtor

Core workflow:

> Buyer tours independently → records photos / voice → AI creates structured questions → buyer shares with Realtor.

Instead of sending random photos/messages, send structured questions linked to evidence.

The Realtor should initially be able to view and answer through a web share page without installing the app.

## Shared Tour Model

Do not architect Buyer Mode and Realtor Mode as separate products.

The central object should be **Tour**.

Participants may include:

- buyer
- spouse / family member
- Realtor

Participants may contribute:

- photos
- voice notes
- comments
- reactions
- answers

Maintain attribution.

This can become a shared home-buying decision workspace without turning into a generic collaboration platform.

## Buyer vs Realtor Value

### Buyer
- remember
- organize
- compare
- ask questions
- decide
- share

### Realtor
- understand buyer preferences
- answer questions
- professional follow-up
- branded Tour Reports
- manage multiple buyers
- improve buyer experience

Use the same Tour data, but do not force identical UI on both roles.

## Monetization Hypothesis

Buyer should initially be free or very low-friction because home buyers are temporary users.

### Buyer — Free
- create tours
- capture photos / voice
- AI summaries
- basic comparisons
- share with Realtor

Possible later limits:
- active tours
- storage
- advanced AI comparisons
- PDF export

### Realtor Pro — Paid
- branded reports
- unlimited clients
- professional templates
- buyer preference insights
- shared workspaces
- follow-up generation
- export
- integrations

Buyer can become a distribution channel into Realtor accounts.

## Growth Loop

> SEO / social content  
> → Buyer discovers free home-tour tool  
> → Buyer uses it during viewings  
> → Buyer shares Tour/questions with Realtor  
> → Realtor discovers product  
> → Realtor uses it with other buyers  
> → Realtor invites new buyers

Potential loop:

> **Buyer → Realtor → Buyer**

## SEO Implications

Buyer-facing topics:

- how to keep track of houses viewed
- home viewing checklist
- how to compare houses when buying
- what to look for when viewing a house
- house hunting notes
- questions to ask after viewing a house
- best app for tracking house viewings
- how to remember houses after showings

CTA:

> **Use the free Home Tour tool.**

Acquisition path:

> **Content → Buyer → Product → Realtor**

## Product Boundaries

Do not turn this into:

- MLS replacement
- Zillow/Realtor.ca competitor
- Realtor marketplace
- mortgage marketplace
- home inspection service
- automated property-condition certification
- general real-estate CRM

Keep the initial problem narrow:

> **Capture, remember and compare homes you personally toured.**

AI observations must not be presented as professional inspection conclusions.

Acceptable:

> “Buyer noticed a damp smell in the basement.”

Not acceptable without verified evidence:

> “The basement has a moisture problem.”

## Suggested Core Data Model

```text
User
  ├── role: buyer | realtor
  └── profile

Home
  ├── address
  ├── listing_metadata
  └── source

Tour
  ├── home
  ├── participants
  ├── started_at
  ├── finished_at
  └── status

Capture
  ├── type: photo | video | voice | text
  ├── content
  ├── timestamp
  ├── room/context
  └── author

Observation
  ├── type: like | concern | question | fact | reaction
  ├── text
  ├── source_capture
  └── confidence

TourSummary
  ├── likes
  ├── concerns
  ├── questions
  ├── overall_impression
  └── editable

Comparison
  ├── tours
  ├── criteria
  └── ai_analysis

Share
  ├── tour
  ├── recipient
  ├── permissions
  └── responses
```

Important architectural principle:

> **Tour should remain the core domain object, not Report.**

A Report is one possible output of a Tour.

## MVP Priority

The first Buyer Self-Tour MVP should prove:

> **Can a buyer walk through a house, casually take photos / voice notes, and leave with a useful structured memory of that home?**

Minimum flow:

1. Create/select property.
2. Start Tour.
3. Capture photos.
4. Capture voice notes.
5. Finish Tour.
6. AI extracts likes / concerns / questions.
7. Generate Tour Summary.
8. Compare at least two Tours.
9. Share Tour Summary/questions by link.

Avoid premature features:

- Realtor CRM
- lead marketplace
- mortgage integration
- listing search platform
- complex scoring
- community
- advanced collaboration

## Key Product Hypothesis

> **After buyers view multiple homes, remembering and comparing what they personally saw is painful enough that they will actively use a mobile capture tool during real showings.**

The strongest validation signal is not “This sounds useful.”

It is:

> **A buyer uses it during one real showing, then voluntarily uses it again during the next showing.**

Treat repeat usage across real home tours as the primary early validation metric.

## Codex Implementation Guidance

Before implementation:

1. Review the existing Realtor Tour/Report workflow and architecture.
2. Reuse existing components and domain models wherever practical.
3. Do not duplicate Buyer and Realtor capture pipelines.
4. Refactor toward `Tour` as the shared domain object if current architecture is overly centered on `Report`.
5. Preserve all existing working Realtor functionality.
6. Implement Buyer Self-Tour incrementally.
7. Keep buyer-specific UI separate from Realtor professional functionality where needs differ.
8. Prefer simple mobile-first flows over configuration-heavy screens.
9. Document schema migrations and architectural decisions.
10. Add automated tests for new core flows.

Support future collaboration architecturally, but **do not build speculative platform features until required by the MVP**.
