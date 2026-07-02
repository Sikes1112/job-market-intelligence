# Layer 26 Guardrails

Layer 26 guardrails keep the career agent grounded, private, and approval-gated.
They apply to grounded answers, action plans, progress memory, and tool
previews.

## Grounding Checks

- Recommendations require structured evidence refs.
- Strategic action-plan steps require evidence refs.
- Tool previews require grounded answer or plan evidence unless the action is
  blocked before execution.
- User preferences and career memory may personalize ranking or explanation,
  but they are never product-owned evidence.
- Fabricated opportunity IDs are blocked unless they match trusted stored
  opportunity evidence.

## Freshness And Uncertainty

- Answers, recommendations, plans, plan steps, and tool previews include
  freshness metadata.
- Answers, recommendations, plans, plan steps, and tool previews include
  uncertainty metadata.
- Forecast-backed outputs must disclose confidence and carry bounded-warning
  language.
- Forecasts are directional signals only and must not be presented as
  guaranteed hiring outcomes.
- Stale, incomplete, low-confidence, partial, or unknown evidence creates
  warnings or limitations.

## Approval Gates

Career-agent tools may prepare, draft, suggest, queue, or preview actions.
They must not silently execute high-impact actions.

Approval is required for:

- reminder creation
- user-specific report export
- watchlist mutation
- notification preference creation or enabling
- employer contact
- outreach sending
- profile sharing
- resume submission
- job application submission

Layer 26C stores approval and rejection records. It does not claim runtime
execution for reminders, exports, notifications, watchlists, outreach, or
applications because those integrations are not wired in this batch.

## Prohibited Actions

- no autonomous job applications
- no resume submission without explicit approval
- no employer contact without explicit approval
- no outreach sending through the career agent
- no profile sharing through the career agent
- no hidden paid, partner, or employer influence
- no fabricated job openings
- no unsupported career claims
- no private memory leakage
- no frontend-only fake execution

## Privacy And Redaction

Private career memory is user-scoped, category-scoped, and private-only.
It does not appear in public routes, public action plans, public reports, or
export-safe payloads unless explicitly requested and still marked as redacted
from public payloads.

Career-agent payloads must not expose:

- private memory through public/export-safe views
- internal review notes
- unsafe source metadata
- private metadata
- raw internal source-link IDs
- internal formula weights

Paid or partner influence may be disclosed when evidence contains it, but it
must not silently bias ranking or authorize tool execution.

## False-Integration Protections

- Tool preview records include `runtime_execution_performed`.
- Approval responses keep `runtime_execution_performed: false` unless a real
  backend runtime path exists.
- Frontend approval controls call protected backend endpoints and render backend
  status; they do not locally mark actions executed.
- Public demo denies protected memory and tool routes.
- Blocked application actions remain blocked even if an approval object exists.
