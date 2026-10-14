# AI implementation planner and vendor scorecard

Where: AI track > AI implementation planner. Code: `backend/app/services/ai_impl.py`, `ai_vendor.py`, `routers/aiimpl.py` (`/api/aiimpl/...`), `panels/ImplPanel.tsx`, `VendorTab.tsx`.

Sources: a one-page guide on moving AI from a demo to a measured result, and a vendor's 25-question AI software checklist for small businesses. Both are vendor marketing; the scales, weights, gates and thresholds here are this app's own rules of thumb, not standards.

## Tools
- **Readiness**: score value, frequency, process stability, measurability and risk from 1 to 5; names the fix for each weak one.
- **Seven-stage checklist**: outcome, process, exceptions, data and security audit, human/AI split, trial, expansion.
- **Exception map**: `case | share % | rule-based yes/no | owner | failure`. Shows the predictable share and exceptions with no owner.
- **Autonomy level**: four levels (assist, supervised, bounded, broad) from error cost, reversibility, regulation, and the Wilson lower bound of reviewed accuracy.
- **What can I claim?**: model works, fits the workflow, used, business number moved; subtracts tool cost.
- **Vendor scorecard**: the 25 original questions plus 7 extra (exit/export, uptime commitment, activity log, human override, own accuracy test, breach notice, total cost). Weighted, with must-pass gates; unknown is not yes.

## Mistakes found in the sources
See `SLIPS` in each service (shown in the app). Main ones: no scale for readiness; "fix the process first" is too absolute; equal weights let a vendor reach "Ideal" while failing security; two of the 25 questions are about the buyer, not the software; the 47% statistic has no source; SOC 2 is an audit report, not a regulation.

## Not buildable
Observing a real workflow, verifying vendor claims, contract and legal review, running AI in a live workflow.
