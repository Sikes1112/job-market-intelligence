Object State Model

Lifecycle States, Transitions, Read/Write Rules, and UI Behavior
This defines:
* what state each major object can be in
* how objects move between states
* what jobs are allowed to read or write those states
* what the UI should do when an object is in each state
* how stale, partial, failed, and low-confidence data should behave
This is the final control layer that makes the orchestration system usable.

⸻

1. Purpose
The app has now been defined in terms of:
* research workflow
* jobs
* triggers
* queues
* workers
* retries
* dependencies
But the system still needs one more thing:
a formal lifecycle model for every major object
Without this, the app will not know:
* whether a region page is safe to show
* whether a company object is stale or invalid
* whether a comparison can be trusted
* whether a rebuild should block or degrade gracefully
That is what this solves.

⸻

2. Core Object Types
The state model should apply to these major objects:
1. Geography Object
2. Candidate Company Pool
3. Classified Company Record
4. Company-Region Presence Record
5. Company-Region Hiring Record
6. Company-Region Entry-Level Record
7. Region Market Score Object
8. Region Output Object
9. Company Output Object
10. Comparison Output Object
11. Contextual Challenge Object
12. Personalized Output Object
13. Audit Report
Not all objects need exactly the same states, but they should use a common state language.

⸻

3. Core State Set
These are the main lifecycle states the system should use.
3.1 
new
Object has been declared or requested but not yet built.
Example:
* new region added, but no market data built yet
3.2 
building
A job is actively constructing or rebuilding the object.
3.3 
fresh
Object is built, valid, and within freshness tolerance.
3.4 
stale
Object exists and may still be usable, but freshness is outside the preferred window.
3.5 
partial
Object exists, but some expected subcomponents are missing or incomplete.
3.6 
low_confidence
Object exists, but confidence is degraded due to ambiguous evidence, incomplete inputs, or soft failures.
3.7 
failed
The most recent attempt to build or refresh the object failed.
3.8 
blocked
Object cannot be built because a required upstream dependency is missing, invalid, or failed.
3.9 
rebuilding
A valid older version exists, but a newer build is currently in progress.
This is different from building, because there is already a usable prior version.
3.10 
deprecated
Object exists, but should no longer be used because it has been superseded or invalidated by rules/structure changes.
3.11 
verified
Object is not only fresh, but has passed the required integrity/audit checks.
This is a stronger state than plain fresh.

⸻

4. Common State Metadata
Every major object should carry these metadata fields.
{
  "object_id": "string",
  "object_type": "string",
  "state": "new | building | fresh | stale | partial | low_confidence | failed | blocked | rebuilding | deprecated | verified",
  "version": "string",
  "created_at": "ISO-8601 timestamp",
  "updated_at": "ISO-8601 timestamp",
  "last_successful_build_at": "ISO-8601 timestamp or null",
  "last_attempted_build_at": "ISO-8601 timestamp or null",
  "freshness_expires_at": "ISO-8601 timestamp or null",
  "confidence_level": "high | medium | low | unknown",
  "dependency_refs": [],
  "blocking_reason": null,
  "failure_reason": null,
  "source_job_id": "string or null"
}
This gives the orchestrator and UI enough context to behave properly.

⸻

5. State Semantics
new
Meaning
The object has been created conceptually but has no usable built payload yet.
UI behavior
* show loading/setup state
* do not present as ready
Scheduler behavior
* eligible for initial build job
Read rule
* not safe for standard product reads

⸻

building
Meaning
First-time build is in progress and no prior usable version exists.
UI behavior
* show loading
* may show placeholder shell only
Scheduler behavior
* block duplicate build jobs with same dedupe key
* allow observers to subscribe for completion
Read rule
* do not use as canonical payload

⸻

fresh
Meaning
The object is current enough for normal use.
UI behavior
* show normally
* no freshness warning
Scheduler behavior
* no immediate rebuild needed unless triggered by event
Read rule
* fully readable
* safe default for product surfaces

⸻

stale
Meaning
The object is older than preferred freshness tolerance, but still usable.
UI behavior
* show object with freshness note if relevant
* often better than blank failure
Scheduler behavior
* enqueue refresh when appropriate
* may increase priority if heavily viewed
Read rule
* readable if no fresher valid version exists
* safe fallback for many user views

⸻

partial
Meaning
The object exists, but some expected components are missing.
Example
A region output exists, but entry-level summary failed to build.
UI behavior
* show available components
* hide or mark missing components
* do not silently treat missing as zero
Scheduler behavior
* enqueue targeted repair/rebuild
* preserve usable subcomponents
Read rule
* readable with degraded treatment
* downstream jobs may use if rules permit

⸻

low_confidence
Meaning
The object exists, but evidence quality is degraded.
Example
A company-region presence record was built from weak office evidence without strong hiring confirmation.
UI behavior
* show result with lower-confidence indicator where relevant
Scheduler behavior
* eligible for repair, evidence review, or audit follow-up
Read rule
* readable, but should not be treated like high-confidence truth in all scoring contexts

⸻

failed
Meaning
The most recent build or refresh attempt failed and no successful current output was produced.
UI behavior
* if prior usable version exists, show prior version with degraded status
* otherwise show error/unavailable state
Scheduler behavior
* evaluate retry policy
* may escalate if failure repeats
Read rule
* failed version itself is not canonical
* may fall back to prior successful version if available

⸻

blocked
Meaning
The object cannot be built because an upstream dependency is missing or invalid.
Example
Region output blocked because region score object failed.
UI behavior
* show unavailable or waiting state
* ideally include generic “updating data” message, not technical details
Scheduler behavior
* do not retry object build until dependency state changes
* watch dependency events
Read rule
* not readable as current object
* may fall back to older version if safe

⸻

rebuilding
Meaning
A valid current object exists, but a replacement build is underway.
UI behavior
* show current object
* optionally indicate refresh in progress
Scheduler behavior
* keep serving old version until new one commits successfully
Read rule
* use existing committed version until replaced

⸻

deprecated
Meaning
The object should no longer be used because a structural or semantic change made it obsolete.
Example
Old region output built against outdated geography definitions.
UI behavior
* never show in normal product flow
Scheduler behavior
* safe to purge or archive
* downstream jobs should not depend on it
Read rule
* unavailable for canonical reads

⸻

verified
Meaning
The object is fresh and has passed required audit/integrity checks.
UI behavior
* show normally
* no special badge needed unless product wants trust indicators
Scheduler behavior
* highest trust state
* preferred for downstream reads
Read rule
* ideal state for scoring and comparison

⸻

6. State Transition Model
Here is the core transition logic.
Standard happy path
new→ building→ fresh→ verified
or
fresh→ rebuilding→ fresh→ verified
Time decay path
fresh→ stale
Partial build path
building→ partial
or
rebuilding→ partial
Confidence downgrade path
fresh→ low_confidence
or
partial→ low_confidence
Failure path
building→ failed
or
rebuilding→ failed
Dependency blockage path
new→ blocked
or
stale→ blocked
if rebuild is required but dependencies unavailable
Obsolescence path
fresh→ deprecated
or
stale→ deprecated
when structural rules change

⸻

7. Transition Rules by Cause
Cause: first-time build requested
* new → building
Cause: build success
* building → fresh
* rebuilding → fresh
Cause: audit passed
* fresh → verified
Cause: freshness window expired
* fresh → stale
* verified → stale
Cause: partial upstream failure
* building → partial
* rebuilding → partial
Cause: evidence ambiguity
* fresh → low_confidence
* partial → low_confidence
Cause: hard failure
* building → failed
* rebuilding → failed
Cause: missing dependency
* new → blocked
* rebuilding → blocked
Cause: successful repair
* failed → building
* partial → rebuilding
* low_confidence → rebuilding
* blocked → building once dependency restored
Cause: structural invalidation
* any active usable state → deprecated

⸻

8. Object-Specific State Rules
Not every object should use every state equally.

⸻

8.1 Geography Object
Important states
* new
* building
* fresh
* verified
* failed
* deprecated
Rare states
* partial
* low_confidence
Notes
Geography objects are foundational and should usually be clean, not fuzzy.

⸻

8.2 Candidate Company Pool
Important states
* new
* building
* fresh
* stale
* failed
* deprecated
Notes
This is intake-stage data, so verified may be less important than for downstream truth objects.

⸻

8.3 Classified Company Record
Important states
* fresh
* verified
* low_confidence
* failed
* deprecated
Notes
A company classification may reasonably be low_confidence if included via override or edge-case logic.

⸻

8.4 Company-Region Presence Record
Important states
* fresh
* verified
* low_confidence
* partial
* failed
Notes
This is one of the most likely places to have low-confidence states because evidence can be ambiguous.

⸻

8.5 Company-Region Hiring Record
Important states
* fresh
* stale
* partial
* failed
* rebuilding
Notes
This is a dynamic object that will often cycle between fresh and stale.

⸻

8.6 Company-Region Entry-Level Record
Important states
* fresh
* stale
* partial
* low_confidence
* failed
Notes
This should support degraded-confidence states when entry-level metadata is incomplete.

⸻

8.7 Region Market Score Object
Important states
* fresh
* stale
* partial
* failed
* verified
Notes
This is one of the most important objects in the app, so stale handling must be graceful but disciplined.

⸻

8.8 Region Output Object
Important states
* fresh
* stale
* partial
* rebuilding
* failed
Notes
This is heavily user-facing, so fallback behavior matters a lot.

⸻

8.9 Company Output Object
Important states
* fresh
* stale
* partial
* rebuilding
* failed

⸻

8.10 Comparison Output Object
Important states
* fresh
* stale
* partial
* failed
* blocked
Notes
Comparison objects are downstream and can often be rebuilt cheaply, so stale is usually acceptable briefly.

⸻

8.11 Contextual Challenge Object
Important states
* fresh
* stale
* failed
* blocked
Notes
This is advanced-mode output, so degraded availability is more acceptable than for core region views.

⸻

8.12 Personalized Output Object
Important states
* fresh
* stale
* failed
Notes
This is usually session-scoped and lightweight. It should fail fast and degrade simply.

⸻

8.13 Audit Report
Important states
* fresh
* stale
* failed
Notes
Audit reports are meta-objects. They influence trust and control, not direct user content.

⸻

9. Read Rules by State
This is critical.
Safe for normal UI reads
* fresh
* verified
* stale if within allowed stale tolerance
* rebuilding if prior committed version exists
* partial only if product supports partial rendering
Safe only for guarded/internal reads
* low_confidence
* partial
* stale beyond soft threshold but within hard threshold
Not safe for normal reads
* new
* building
* failed
* blocked
* deprecated
These should use fallback logic instead.

⸻

10. Write Rules by State
Objects that can be written/replaced directly
* new
* building
* rebuilding
* stale
* partial
* low_confidence
* failed
* blocked
Objects that should not be mutated in place casually
* verified
For verified, prefer:
* create new version
* validate
* then atomically replace
Objects that should not be reused as canonical targets
* deprecated

⸻

11. UI Behavior Rules
This is where the state model becomes product behavior.
Region page
If state is 
fresh
or 
verified
Show normally.
If 
stale
Show page with freshness note if needed.
If 
rebuilding
Show current page and silently refresh if possible.
If 
partial
Show available sections and mark unavailable sections.
If 
failed
and prior version exists
Show prior version with degraded state.
If 
failed
and no prior version
Show unavailable/loading-retry state.

⸻

Company page
Same general logic as region page, but company-level.

⸻

Comparison page
If both region outputs are 
fresh
Show normal comparison.
If one or both are 
stale
Show comparison with freshness note.
If one is 
partial
Show partial comparison, do not fake missing categories.
If one is 
blocked
or 
failed
with no fallback
Block full comparison and show unavailable/partial message.

⸻

Personalized discovery
If base market truth is 
fresh
Apply overlay normally.
If base truth is 
stale
Allow with freshness notice.
If base truth is 
failed
or 
blocked
Block personalized ranking for affected scope.

⸻

12. Freshness Threshold Logic
Every object type should define two freshness thresholds.
Soft threshold
After this point:
* object becomes stale
* still readable
Hard threshold
After this point:
* object may no longer be safe for normal UI use
* fallback or rebuild required
Example conceptually:
* hiring data may have a shorter threshold
* geography definitions may have a very long threshold
* company outputs may inherit thresholds from hiring and region truth
This should be per-object-type, not global.

⸻

13. Confidence Logic
State and confidence are related, but not identical.
State answers:
“What lifecycle condition is this object in?”
Confidence answers:
“How much should we trust the content of this object?”
So an object can be:
* fresh + medium confidence
* partial + low confidence
* stale + high confidence
* verified + high confidence
That distinction matters.
Recommended confidence enum:
* high
* medium
* low
* unknown

⸻

14. Dependency-State Rules
Downstream jobs should inspect upstream object states before reading them.
Allowed upstream read states for downstream jobs
Usually:
* fresh
* verified
* sometimes stale
* sometimes partial if job contract allows degraded mode
Disallowed upstream read states
* new
* building
* failed
* blocked
* deprecated
Conditional state
* low_confidencemay be allowed for some downstream jobs, but only if explicitly permitted
Example:
* presence mapping with low confidence may still feed region outputs
* but maybe not verified scoring mode

⸻

15. Repair Rules by State
If object is 
stale
Enqueue refresh job.
If object is 
partial
Enqueue targeted repair or rebuild job.
If object is 
low_confidence
Enqueue evidence repair, audit, or confidence upgrade job when valuable.
If object is 
failed
Apply retry policy, then escalate.
If object is 
blocked
Wait for dependency resolution event, then retry.
If object is 
deprecated
Do not repair. Rebuild against new structure instead.

⸻

16. Recommended State Machine by Layer
Market truth layer
Objects:
* classified company
* presence
* hiring
* entry-level
Preferred states:
* fresh
* verified
* stale
* low_confidence
Avoid relying heavily on:
* partial
because this layer drives truth.
Intelligence layer
Objects:
* region scores
* region outputs
* company outputs
* comparisons
Preferred states:
* fresh
* stale
* rebuilding
* partial
because graceful degradation matters more here.
Personalization layer
Objects:
* personal rankings
* personal targets
* personal comparison overlays
Preferred states:
* fresh
* stale
* failed
because these are lightweight and user-specific.

⸻

17. Minimal State Transition Table
From	Event	To
new	build started	building
building	success	fresh
fresh	audit pass	verified
fresh	freshness expired	stale
stale	rebuild started	rebuilding
rebuilding	success	fresh
building/rebuilding	partial success	partial
partial	repair started	rebuilding
fresh/partial	confidence downgrade	low_confidence
building/rebuilding	hard failure	failed
new/stale/rebuilding	dependency missing	blocked
blocked	dependency restored	building or rebuilding
any active state	structural invalidation	deprecated

⸻

18. MVP State Model Recommendation
For a realistic MVP, keep it simpler.
You probably only need these states first:
* new
* building
* fresh
* stale
* partial
* failed
* blocked
* rebuilding
Then add:
* low_confidence
* verified
* deprecated
once the integrity layer matures.
That is likely the right practical order.

⸻

19. Strongest Design Rule
If I had to compress the whole state model into one sentence:
serve fresh when possible, stale when safe, partial when honest, and never pretend failed or blocked objects are complete.
That is the trust rule of the product.

⸻