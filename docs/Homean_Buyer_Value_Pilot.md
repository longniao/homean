# Homean buyer-value pilot

Status: proposed experiment, not validated positioning or permission to enroll customers.
Prepared September 10, 2026. Complements the existing
[Pilot Acceptance Checklist](Homean_Pilot_Acceptance_Checklist.md); it does not
mark any release, consent, provider, or device gate as passed.

## Decision we are trying to make

Should Homean become a paid tool for active buyer's agents because it helps their
buyers remember homes, compare trade-offs, and resolve questions with less agent
follow-up work?

Primary user: buyer's agent. Beneficiary: buyer household. Initial paying customer:
individual agent. The report is a delivery format, not the customer outcome.
Direct-to-buyer distribution is a separate hypothesis, not the default: a buyer
has an episodic purchase journey, while an agent can use the product across clients.
Neither willingness to pay nor retention is established.

Proposed message to test:

> Help your buyers remember every home, compare the trade-offs, and know what to check next.

Keep the frozen product documents unchanged. This proposal refines what to test;
it does not authorize new roadmap features. Do not claim the BC commission reform
asserted in Product v1.1 is established: the BCFSA material reviewed describes
proposals and does not support that full claim.

## The uncomfortable hypotheses

1. Agents may not currently write reports. Homean could add work instead of removing it.
2. Buyers may enjoy the presentation but never use it in a later conversation or decision.
3. Recording during a showing may be socially awkward or distract from the client.
4. A good agent may already provide the same outcome with photos and a voice message.
5. A detailed record may help the agent while omitting what the buyer actually cares about.
6. AI correction and review time may consume the promised savings.
7. Free pilot use may disappear when reminders, founder assistance, or subsidies stop.

A pilot is useful only if these hypotheses can fail visibly.

## Participants and sequence

Recruit five agents with upcoming multi-property buyer tours. Include agents who
already send detailed follow-up and agents who mostly use informal messages.
Select for actual tour activity, not the label 'exclusive buyer's agent'. Start
with English-language workflows to match v1. Include a mix of local and remote
buyer situations if available; five participants cannot support segment-level
statistical conclusions.

Recruitment and scheduling have not started. All messages below are drafts.

1. Interview five agents and, with their participation agreed, buyer households.
   Use redacted past examples before requesting any new capture.
2. Observe at least one baseline tour day per agent using their normal method.
   Do not ask them to produce a report they would not ordinarily create.
3. Complete the applicable release gates before live customer capture. Current
   infrastructure readiness does not establish real AI or physical-device quality.
4. Run two weeks of tool use, aiming for at least 20 eligible property visits in
   total. If participants have too few tours, extend observation rather than count
   inactivity as rejection. Record reminders and assistance separately.
5. Review the evidence and offer a clearly stated paid continuation, with price,
   currency, included usage, and period fixed before presenting it. No price is
   established here; hypothetical acceptance is not payment. Billing requires its
   applicable readiness checks before any charge.

## Discovery guide: behavior before opinions

Agent interview, approximately 20 minutes:

- Walk me through your last day showing several homes to one buyer.
- What did you record, and what did you actually send afterward? Show a redacted example.
- How long did each step take? Which steps did you skip?
- What did the buyer ask again later? How did you find the answer?
- Tell me about the last time two homes were confused or an important question was missed.
- What would prevent you from capturing notes during a showing?
- Which existing tool or task would Homean replace? If none, what would justify the extra work?

Buyer interview, separately where practical:

- Thinking about your last tours, which homes are still difficult to distinguish?
- How did you and anyone buying with you compare your reactions afterward?
- What information did you need to ask for again?
- Show how you kept your shortlist. What changed it?
- What did the agent's follow-up help you do? What was missing?

Avoid 'Would you use AI reports?' and 'Does this look professional?' as evidence of
need. Distinguish actual incidents from anticipated benefits. Do not collect
unneeded financial details, addresses, or identifying information in repository logs.

## Test the capture method, not just the report

Where consent and the setting permit, compare:

A. Capture during the showing, followed by review.
B. Selected photos plus an agent voice debrief immediately afterward.

Let each agent try both on comparable visits; alternate the order where practical.
Record visits where either method is unsuitable and why. Do not randomize anything
that would override participants' preferences or permission. This is a small
qualitative comparison, not a causal trial.

Use the same report structure for both methods. Record capture time, correction
work, omissions, and the agent's unprompted choice on a subsequent visit. A faster
method is not better if it loses a material buyer concern.

## Output to test using the existing workflow

Start with a brief recap visible on a phone, with optional supporting detail:

1. What stood out for this buyer, tied to needs they actually expressed.
2. Trade-offs and concerns, without invented conclusions.
3. Questions still open, with a named follow-up owner where one was agreed.
4. Selected photos and the available evidence supporting the observations.

After multiple visits, use the existing agent comparison view to facilitate a
shortlist conversation. Do not imply that buyers already have an interactive
comparison portal or preference-editing feature. Gather their corrections manually
and record that assistance. A mock-up or manually prepared example is labeled as such.

Illustrative example only — not a real property assessment:

| Item | Useful recap |
| --- | --- |
| Buyer need | Space for a parent who has difficulty with stairs |
| Observed | Three steps at the entrance during this visit |
| Buyer reaction | Buyer liked the ground-floor bedroom |
| Reported claim | Listing representative said a ramp could be installed; unverified |
| Open question | Ask the relevant professional about feasibility before relying on it |

A buyer reaction, an observation, a third-party claim, and a verified fact must
remain distinct. Missing information is shown as unknown. Agent confirmation
approves the report; it does not independently verify every underlying claim.

## Measures and definitions

| Measure | Definition |
| --- | --- |
| Eligible visits | Visits within agreed pilot scope, whether Homean was used or not; record exclusion reasons before calculating adoption |
| Voluntary use | Agent starts another visit without a reminder specific to that visit |
| Agent effort | Capture administration + upload handling + correction + review + delivery + subsequent clarification time |
| Baseline difference | Within-agent comparison with their normal workflow; report per-agent results, not only a pooled average |
| Review burden | Active review/correction minutes and number/type of substantive edits |
| Buyer use | Buyer can identify a specific later action or conversation informed by the recap or comparison |
| Decision support | A report helped recall a detail, identify a missing answer, clarify a trade-off, or discuss a shortlist; it need not lead to an offer |
| Material error | Unsupported or misattributed content that could change interpretation of the property or buyer preference |
| Delivered report | Agent-confirmed report shared with intended buyer; link creation alone is not confirmed receipt |
| Paid continuation | Actual payment for the disclosed period; promises and failed checkout attempts are recorded separately |

Record time spent helping by the founder/operator. Report performance both with
and without that assistance. A report open or download is engagement, not proof of
value. Do not optimize for faster offers or more transactions as a proxy for a
better buyer decision.

## Provisional decision thresholds

These are proposed decision rules, not industry benchmarks or statistical proof.
Agree them before enrollment; preserve the original rules if later revised.

Proceed to a larger pilot only if:

- At least three of five agents voluntarily reuse Homean in week two and choose
  paid continuation after experiencing it.
- At least three of five agents show lower median total effort on comparable
  visits, or demonstrate a specific new buyer benefit worth the extra effort.
  Report these two routes separately; do not relabel added work as time saved.
- At least half of participating buyer households interviewed describe a specific
  useful later action or conversation; publish the denominator and missing responses.
- No material AI error reaches a buyer in the observed sample. Any such incident
  pauses that output path for investigation and retesting. This threshold is a
  pilot stop rule, not a claim that zero future errors are possible.

Interpret mixed outcomes:

| Evidence | Next decision |
| --- | --- |
| Recaps are used, but correction is expensive | Improve capture and draft accuracy before expanding scope |
| Buyers use comparisons, but ignore long reports | Test a shorter recap and make comparisons more prominent |
| Post-tour debrief wins on use and effort | Simplify around debriefs; preserve other capture as optional |
| Agents deliver reports, buyers cannot explain a benefit | Reconsider the output and buyer relevance; delivery is insufficient |
| Value appears only with founder assistance | Identify the assisted steps before claiming scalable demand |
| Repeated use disappears or no one pays | Revisit segment/problem fit before adding CRM or team features |

## Draft recruitment message — not sent

> I'm testing Homean with a small number of agents who regularly show several homes
> to the same buyer. It turns showing notes and photos into a reviewed recap to help
> buyers remember the differences and follow up on unanswered questions. I'd like to
> understand how you handle that today before asking you to try anything. Would you
> be open to a 20-minute conversation using a redacted example of your usual follow-up?

## Evidence log template

Use participant codes. Keep consent records and original customer material in the
approved private location, not in git. Blank rows are templates, not observations.

| Date | Agent code | Buyer code | Baseline/tool | Capture method | Eligible/used | Agent minutes by step | Operator minutes | Substantive edits | Delivered/received | Specific buyer use | Evidence reference |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| | | | | | | | | | | | |

| Hypothesis | Current evidence | Contradictory evidence | Participants observed | Decision | Next experiment |
| --- | --- | --- | --- | --- | --- |
| Agents save total effort | Not collected | Not collected | 0 | Unvalidated | Observe baseline |
| Buyers use the output later | Not collected | Not collected | 0 | Unvalidated | Interview after tours |
| Capture fits the showing | Not collected | Not collected | 0 | Unvalidated | Compare capture methods |
| Agents will pay | Not collected | Not collected | 0 | Unvalidated | Paid continuation after experience |

## Sources and limits

- [Homean Product Document v1.1](Homean_Product_Document_v1.1.md) and
  [Roadmap v1.2](Homean_Full_Feature_Roadmap_v1.2.md): existing product assumptions.
- [NAR 2025 buyer/seller findings](https://www.nar.realtor/news/real-estate-news/nar-2025-profile-of-home-buyers-sellers-reveals-market-extremes):
  U.S. evidence about what buyers seek from agents; not Homean demand validation.
- [BCFSA discussion paper](https://www.bcfsa.ca/media/4475/download):
  proposals do not establish the full commission-reform claim in Product v1.1.

No customer interviews, pilot outcomes, recruitment, payment, or real-provider AI
results are asserted by this document.
