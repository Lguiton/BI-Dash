"""How to do it / how to fix it for Computer engineering, AI engineering, ML/NLP/deep learning, Project management and Full stack.

Plain-English guides with steps, a way to check it worked, time and cautions. Nothing here changes anything. Search can be limited to one field."""
from __future__ import annotations

import json
import re

GUIDES: list[dict] = []
REF: dict[str, str] = {}
CPE, AI, ML, PM, FS = "Computer engineering", "AI engineering", "ML, NLP and deep learning", "Project management", "Full stack"
AREAS = [CPE, AI, ML, PM, FS]


def _g(gid, area, title, keywords, why, steps, verify, minutes, caution="", tool="", refs=()):
    GUIDES.append({"id": gid, "title": title, "area": area, "keywords": keywords, "why": why, "steps": list(steps), "verify": verify, "minutes": minutes, "caution": caution, "tool": tool})
    for r in refs:
        REF[r] = gid


# ------------------------------------------------------------------ Computer engineering
_g("cpe-level", CPE, "A 5 V part connected to a 3.3 V board", "level shifter 5v 3.3v logic voltage esp32 pico raspberry pi damage divider mismatch", "3.3 V pins can be damaged by 5 V signals, and some 5 V parts do not read 3.3 V signals reliably.",
   ["Find the part's logic voltage in its datasheet.", "For a signal going INTO the board from a 5 V part, add a level shifter module or a two-resistor voltage divider (for example 1 kilo-ohm over 2 kilo-ohm).", "For a signal going OUT of the board to a 5 V part, check the part's 'input high' voltage: many accept 3.3 V, some do not.", "Join all grounds together.", "Power the part from its own 5 V rail, never from a 3.3 V pin."],
   "Measure the signal with a meter: it must never go above the board's logic voltage on a board pin.", 20, "Test with the part powered but the board disconnected first.", "Parts list checker", ("level_shift",))
_g("cpe-power", CPE, "Board resets or misbehaves when a motor, relay or radio switches on", "brownout reset power supply current motor relay wifi dip voltage capacitor", "The supply cannot deliver the sudden current, so the voltage dips and the board restarts.",
   ["Add up the worst-case current of everything (the parts list checker does this) and keep it under 80% of the supply's rating.", "Power motors, servos and relays from their own supply, with the grounds joined.", "Add a 100 microfarad capacitor close to the board's power pins and 0.1 microfarad across motor terminals.", "Use a shorter, thicker power cable.", "Add a flyback diode across relay and motor coils."],
   "Watch the board's supply pin with a meter while the load switches: it should stay within 5% of normal.", 30, "", "Parts list checker", ("supply_overload",))
_g("cpe-pins", CPE, "Not enough pins", "pins gpio expander i2c shift register not enough io pins", "Every sensor or button wants a pin, and boards run out.",
   ["List the parts and the pins each needs.", "Use I2C parts (two wires shared by many devices) where you can.", "Add a shift register or an I2C port expander for buttons and LEDs.", "Avoid pins with special jobs (boot, flash, serial) on the ESP32 and Pico.", "Or move to a bigger board."], "The parts list checker shows pins needed under pins available.", 20, "", "Parts list checker", ("pins_exceeded",))
_g("cpe-battery", CPE, "Battery dies much sooner than the estimate", "battery life runtime sleep deep sleep current drain lithium estimate", "Average current is dominated by whatever is on the longest, and radios and regulators waste more than expected.",
   ["Measure the real current with a meter in series, in both active and sleep states.", "Put the board into deep sleep between readings and turn off sensors and radios you are not using.", "Use a low-quiescent-current regulator, not a basic one that burns 5 mA by itself.", "Send data in batches, not every reading.", "Re-run the runtime estimator with the measured numbers."], "A day of real measurement matches the estimate within about 20%.", 60, "Never short or puncture lithium cells. Use a protected battery and charger made for it.", "Battery runtime estimator")
_g("cpe-sensor-noise", CPE, "Sensor readings jump around", "noisy sensor analog adc jitter averaging debounce filter wires", "Long wires, a weak supply and electrical noise all show up in analog readings.",
   ["Take several readings and use the median or average.", "Keep sensor wires short and away from motors and power lines.", "Add a 0.1 microfarad capacitor across the sensor's power pins.", "On an ESP32, avoid ADC2 pins while Wi-Fi is on.", "For buttons, wait 20 to 50 milliseconds after a change before trusting it (debounce)."], "Ten readings of a steady input stay within a small band.", 25)
_g("cpe-wont-boot", CPE, "A board or PC will not start", "no power not booting dead fault finding multimeter short continuity smell", "Most dead boards have a short, a wrong supply or a loose connection.",
   ["Unplug everything and look for burn marks, swollen capacitors and loose connectors.", "Power the bare board alone, with a current-limited supply if you have one.", "Measure the voltage rails: you should see the expected volts on each.", "Use the meter's continuity beep, with power off, to check supply and ground are not joined.", "Add parts back one at a time, powering up after each, until it fails."], "The board powers up bare, and the failing part is found by adding things back.", 45, "Do not open a power supply unit: it holds dangerous voltage even when unplugged.", "Test plan")
_g("cpe-pc-build", CPE, "Planning a PC build that works first time", "pc build parts compatibility cpu socket ram psu wattage cooler case", "Most build problems are mismatched sockets, RAM type and power.",
   ["Pick the CPU, then a motherboard with the same socket and chipset support.", "Match the RAM type (DDR4 or DDR5) to the board.", "Add up the components' power and choose a supply with about 30% headroom.", "Check the cooler fits the case and the CPU socket.", "Check the case fits the graphics card length."], "Every part's specification sheet lists the others as compatible.", 40, "", "Parts list checker")
_g("cpe-docs", CPE, "Writing documentation a client can use", "documentation handoff wiring diagram bill of materials manual photo", "A project nobody can repair or repeat is only half delivered.",
   ["Make a parts list with prices and where each part came from.", "Draw or photograph the wiring and label every wire.", "Include the code with comments, and say which software version it was built with.", "Write the first-power-up and test steps (use the test plan page).", "Add a one-page 'if it stops working' section."], "Someone who was not there can rebuild it from your pages.", 60, "", "Test plan")

# ------------------------------------------------------------------ AI engineering
_g("ai-eval-regress", AI, "The assistant got worse after a change", "evals regression prompt change worse accuracy test suite model update", "Without tests, a prompt or model change can quietly break things that worked.",
   ["Run the same test suite before and after the change.", "Open the comparison: which cases got worse?", "Look at those answers and decide whether the test or the change is wrong.", "Fix the prompt for those cases, or revert, and run again.", "Only ship when the pass rate is at least as good and nothing important regressed."], "The compare line says 0 cases got worse.", 30, "", "Eval runner", ("eval_regression",))
_g("ai-evals-start", AI, "Building a first test suite for an assistant", "eval test cases suite write tests prompts golden answers", "You cannot improve what you cannot measure.",
   ["Collect 20 real questions the assistant should handle, plus 5 it should refuse or say it does not know.", "For each, write rules, not a full answer: words that must appear, words that must not, a length limit.", "Run it and read every failure by hand.", "Add a new case every time you find a real mistake.", "Keep the suite in the handoff pack."], "A suite of at least 20 cases that you trust to catch a real mistake.", 90, "", "Eval runner")
_g("ai-hallucination", AI, "The assistant states things that are not true", "hallucination made up wrong facts confident citations grounding sources", "Language models write plausible text, not verified facts.",
   ["Give it the source text to answer from and tell it to use only that.", "Require it to quote or cite the source, and show the source to the user.", "Tell it to say 'I don't know' when the source does not cover the question, and test that case.", "Add tests with questions that have no answer in the source.", "Keep a person in the loop for anything that matters."], "On your 'no answer' test cases it declines instead of inventing.", 60, "", "Eval runner")
_g("ai-cost", AI, "The AI bill is higher than expected", "cost tokens bill expensive price reduce usage model tier caching", "Every word in and out is billed, and chat history is re-sent each time.",
   ["Estimate it: requests per day, tokens in and out, price per million (cost estimator).", "Trim long instructions and send only the history that is needed.", "Use a smaller model for simple steps.", "Reuse answers to repeated questions.", "Set a monthly spending limit with the provider and an alert at 80%."], "Estimated and actual monthly cost agree within about 20%.", 30, "", "LLM cost estimator", ("cost_high",))
_g("ai-injection", AI, "Text in a document or web page tries to control the assistant (prompt injection)", "prompt injection untrusted text jailbreak tool abuse security documents web", "The model cannot reliably tell your instructions from instructions hidden in the text it reads.",
   ["Treat everything the assistant reads as data, never as orders.", "Give it the fewest tools possible and make any action that changes something need a person's confirmation.", "Never let it see secrets or other customers' data.", "Test with documents that say 'ignore your instructions'.", "Log what it did so you can review it."], "A document with a hidden instruction does not change its behavior.", 60, "No prompt can fully prevent this. Limit what the assistant can do instead.", "AI risk register")
_g("ai-private", AI, "Keeping private data out of an AI service", "privacy personal data pii vendor retention local model redact customer", "Data you send leaves your control under the vendor's terms.",
   ["List what data the assistant sees.", "Remove names, emails, phone numbers and IDs before sending when you can.", "Read the vendor's terms on retention and training, and pick the no-training option.", "For very sensitive text, run a local model instead.", "Tell the client what is sent and where."], "You can state in one sentence what leaves the building.", 45, "Some data (health, children's, financial) carries legal rules. Check them before you build.", "AI risk register")
_g("ai-prompt-version", AI, "Keeping track of prompt changes", "prompt version history diff library change log rollback", "Prompts are code: small edits change behavior.", ["Save every change as a new version with a note on why.", "Compare two versions to see exactly what changed.", "Run the test suite on each version.", "Keep the version number in the handoff pack."], "You can say which prompt version is live and why.", 15, "", "Prompt library")
_g("ai-handoff", AI, "Handing an AI assistant to a client", "handoff deliver client documentation monitoring owner limits training", "A client needs to know what it does, where it fails and who looks after it.", ["Fill in the handoff pack: purpose, instructions, tools, limits, tests, cost.", "Attach the risk register.", "Show the client the failure cases, not only the successes.", "Agree who watches cost and complaints each week.", "Agree how to switch it off."], "The client can explain in their own words what it must not do.", 60, "", "Handoff pack")

# ------------------------------------------------------------------ ML, NLP, deep learning
_g("ml-text-weak", ML, "The text sorter is barely better than guessing", "text classifier weak accuracy labels few examples ambiguous categories tfidf", "Too few examples, or categories that overlap, give a model nothing to learn.",
   ["Read the per-label recall: which categories are failing?", "Look at the failure examples: are the labels themselves inconsistent?", "Merge categories people cannot tell apart, or write a one-line rule for each.", "Add 20 or more clear examples per label, especially like the failures.", "Re-run and compare with the baseline."], "Macro F1 clearly above the baseline, and the failures make sense.", 60, "", "Text classifier", ("text_not_useful",))
_g("ml-low-confidence", ML, "Many texts are marked 'needs a human'", "low confidence needs human threshold uncertain review queue classify", "The model is unsure about text unlike what it learned from.",
   ["Review the flagged texts and label them: they are the most valuable examples.", "Add them to the set and retrain.", "Keep the threshold: a person checking 20% of texts is better than a wrong answer on 20%.", "Raise it for high-stakes categories."], "The share flagged falls as you add examples.", 30, "", "Text classifier", ("needs_human",))
_g("ml-imbalance", ML, "One category is rare and always missed", "imbalance rare class recall minority skewed labels fraud", "A model can score high by ignoring the rare class.", ["Look at recall for the rare class, not accuracy.", "Add more examples of the rare class.", "Check the class weights are balanced (the tool does this).", "Pick the confidence threshold by what a miss costs."], "Recall for the rare class is acceptable to the business.", 40)
_g("ml-extraction", ML, "Extracting fields from documents keeps failing", "extraction regex invoice fields parse pdf layout miss wrong amount", "Layouts vary, and a pattern that fits three samples fails on the fourth.", ["Test the pattern on at least 20 real, varied documents.", "Use the extraction tester: look at missed and wrong fields.", "Add alternative patterns for each layout.", "Always capture a check number (does the total equal the sum of the lines?).", "Send low-certainty documents to a person."], "Recall above 95% on varied samples for each important field.", 60, "", "Extraction tester")
_g("ml-nn-when", ML, "Do I need deep learning?", "deep learning neural network when needed images audio text small data baseline", "Deep learning shines on images, audio and large text sets; for small business tables it rarely beats simpler models.", ["Build the simple baseline first.", "Ask: do I have thousands of examples, or images or audio?", "If not, improve the data before changing the model.", "If yes, try a pre-trained model and fine-tune it, rather than starting from nothing."], "You can show a simple model's score next to the deep one's.", 30, "", "NLP and Deep Learning studio")
_g("ml-overfit", ML, "Great on training data, poor on new data (overfitting)", "overfitting overfit train test gap generalize cross validation regularization", "The model memorized the examples instead of learning the pattern.", ["Compare the score on training rows with the score on held-out rows.", "Use cross-validation, not one split.", "Use fewer inputs and a simpler model.", "Get more data.", "Never tune using the test rows."], "Training and held-out scores are close.", 40, "", "Model Studio")
_g("ml-experiments", ML, "Keeping track of what you tried", "experiment tracking runs results compare parameters metrics reproducible", "Without notes you cannot tell which change helped.", ["Log every run with its settings, the data used and the scores.", "Change one thing at a time.", "Sort by the metric that matters to the business.", "Export the table for the client."], "You can reproduce your best run from the log.", 20, "", "Experiment tracker")
_g("ml-labeling", ML, "Labeling data well", "labeling annotation labels consistent guidelines examples agreement", "Inconsistent labels cap how good any model can be.", ["Write a one-line definition for each label with an example.", "Label 50 texts, then re-label 20 of them a week later and compare.", "Resolve disagreements by editing the definitions.", "Add an 'other' label for text that fits nothing."], "Re-labeling the same texts gives the same labels at least 90% of the time.", 60, "", "Labeling workbench")

# ------------------------------------------------------------------ Project management
_g("pm-scope-creep", PM, "The client keeps adding things (scope creep)", "scope creep change request extra work out of scope client adds sow", "Without a written scope, every extra feels free to the client and costs you.", ["Point to the deliverables list in the statement of work.", "Say yes to the idea and no to the free: 'I can add that, here is the time and price.'", "Write each change as a change request with cost and date effect.", "Get written approval before starting.", "Log the decision."], "Every extra has an approved change request or was declined.", 20, "", "SOW writer")
_g("pm-estimate", PM, "Estimates keep coming in too low", "estimate underestimate hours quote optimistic pert buffer overrun", "People estimate the best case and forget meetings, fixes and waiting.", ["Break the work into tasks under a day or two each.", "Give best, likely and worst-case hours for each.", "Use the estimator and quote near the 80% figure.", "Add a buffer for changes.", "Record actual hours so the next estimate is better."], "Over five projects, actual hours land inside your 80% range four times.", 40, "", "Estimator", ("estimate_wide",))
_g("pm-stories", PM, "Requirements are vague", "requirements user stories acceptance criteria vague unclear definition of done", "'Make it easy to use' cannot be tested, so it cannot be finished.", ["Write each need as: As a [who], I want [what], so that [why].", "Add criteria a tester could pass or fail.", "Replace vague words with numbers.", "Split any story with 'and' in it.", "Have the client sign off on the list."], "Each story has criteria that name an observable result.", 45, "", "User-story writer", ("story_vague",))
_g("pm-late", PM, "The project is late", "late behind schedule delay recovery rescue plan critical path slip", "Lateness compounds: find the cause before adding people or hours.", ["Check the dependency chain: which tasks are on the critical path?", "List what is blocking each late task: a person, a decision or work?", "Cut or defer anything that is not a must-have.", "Tell the client early, with a new date and what changed.", "Re-plan with remaining work only."], "A new finish date everyone has agreed to, with a reason.", 60, "", "Status report")
_g("pm-status", PM, "Writing a status report people read", "status report weekly update client stakeholders health red amber green", "Clients want to know if they are fine, what is next and what you need.", ["Start with one line: on track, watch or at risk, and why.", "List done, in progress and next.", "Show only the top risks with what you are doing.", "End with the decisions you need from them.", "Send it the same day each week."], "The client can answer your questions without a call.", 20, "", "Status report")
_g("pm-risks", PM, "Finding and managing project risks", "risk register probability impact mitigation contingency reserve", "A risk you named is cheaper than one that surprises you.", ["List what could go wrong, by asking 'what would hurt?' for each deliverable.", "Give each a chance and a cost.", "Write one action for each of the top five.", "Review weekly and close the ones that passed.", "Hold a reserve equal to the expected cost of open risks."], "Each top risk has an owner and an action.", 40, "", "Project track")
_g("pm-roadmap", PM, "Deciding what to build first", "prioritize roadmap now next later rice moscow product backlog", "Everything cannot be first.", ["List candidate items and why each matters.", "Score them (reach, impact, confidence, effort) or sort by must, should, could.", "Put 2 to 3 in Now, the next few in Next, the rest in Later.", "Share the roadmap as a direction, not a promise of dates.", "Review monthly."], "Anyone can say what is being built now and why.", 40, "", "Roadmap builder")
_g("pm-decisions", PM, "Nobody remembers why we decided that", "decision log retro retrospective lessons learned record why", "Without a record, decisions get re-argued.", ["Write each decision in one line, with why, options and who decided.", "Set a date to revisit it.", "Hold a short retro after each phase: what went well, what to change, who does what.", "Export the log for the client file."], "You can find the reason for any past decision in a minute.", 15, "", "Decision and retro log")

# ------------------------------------------------------------------ Full stack
_g("fs-no-login", FS, "The scaffolded API has no login", "authentication login auth secure api scaffold protect endpoints jwt session", "Anyone who finds the address can read or change the data.", ["Decide who may do what (read, create, change, delete).", "Add sign-in (session cookie or token) and check it on every route.", "Check ownership: a user may only touch their own rows.", "Rate limit login attempts.", "Test by calling the API without signing in: it must return 401."], "Calling any route without credentials fails.", 90, "Do not build your own password storage: use a proven library and hash with bcrypt or argon2.", "Scaffold writer", ("scaffold_no_login",))
_g("fs-injection", FS, "Stopping SQL injection and bad input", "sql injection parameters bound validation sanitize input escape security", "Pasting user text into SQL lets attackers run their own commands.", ["Always pass values as bound parameters (the ? marks), never join them into the SQL text.", "Validate type, length and allowed values on the way in.", "Use an allow-list for column or table names that come from users.", "Escape text when you put it in a page.", "Test with input like ' OR 1=1 --."], "Odd input is rejected or stored as plain text, and nothing else happens.", 40, "", "Code review report")
_g("fs-api-design", FS, "Designing an API clients can rely on", "api design rest endpoints contract versioning errors status codes openapi", "A clear contract lets the front end and the back end be built separately.", ["List the nouns (orders, customers) and the actions on each.", "Use the right method: GET reads, POST creates, PUT or PATCH changes, DELETE removes.", "Return clear errors with the right status code.", "Write the contract first and agree it.", "Never change a live endpoint's meaning: add a new one."], "A front-end developer can build against the contract alone.", 60, "", "API contract writer")
_g("fs-deploy", FS, "Putting an app on the internet safely", "deploy hosting vps docker https domain server production checklist rollback", "Most launch problems come from skipped basics.", ["Follow the deploy runbook for your host.", "Put secrets in environment variables.", "Turn on HTTPS and automatic renewal.", "Take a backup and know your rollback before you go live.", "Add uptime monitoring."], "The runbook's boxes are all ticked and a rollback has been rehearsed.", 120, "", "Deploy runbook")
_g("fs-bug", FS, "Tracking down a bug", "bug debug error stack trace reproduce logs fix test", "A bug you can reproduce is half fixed.", ["Write exact steps that make it happen every time.", "Read the first error line and the file and line it names.", "Run the code check on the suspect file.", "Narrow it down: halve the code until the bug disappears.", "Write a test that fails, fix it, and see the test pass."], "The failing test now passes and nothing else broke.", 45, "", "Code Workbench")
_g("fs-spreadsheet", FS, "Moving a spreadsheet into a real app", "spreadsheet excel migrate app database web form replace workflow", "A spreadsheet that many people edit eventually breaks.", ["List what each sheet and column means, and who edits what.", "Design tables with a key per row and one fact in one place.", "Import the data into a copy and check the counts.", "Build forms for the edits and a view for the reports.", "Run both side by side for a month, then retire the sheet."], "Totals in the app match the spreadsheet for the same period.", 240, "Keep the original spreadsheet unchanged as a backup.", "Scaffold writer")
_g("fs-quote", FS, "Quoting a software job", "quote price estimate software project hours rate fixed price discovery", "Too low loses money; too vague invites arguments.", ["List the features and give each a low and high hour estimate.", "Add a 20% buffer.", "Multiply by your rate for a range, and quote near the middle for fixed price.", "Write exclusions and a change process.", "Ask for a deposit before starting."], "The quote shows hours, price, payments and what is not included.", 30, "", "Quote helper")
_g("fs-review", FS, "Reviewing code before it ships", "code review checklist quality pull request readability tests maintainability", "A second look catches what tools cannot.", ["Run the automatic checks first.", "Read for naming, one purpose per function and duplicated logic.", "Check inputs are validated and secrets are not in the code.", "Check there is a test for the behavior that matters most.", "Leave suggestions, not orders."], "Every item on the review checklist is answered.", 30, "", "Code review report")


def get(gid: str) -> dict | None:
    return next((g for g in GUIDES if g["id"] == gid), None)


def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 2}


def search(q: str, area: str | None = None, limit: int = 6) -> list[dict]:
    qw = _words(q)
    if not qw:
        return []
    out = []
    for g in GUIDES:
        if area and g["area"] != area:
            continue
        kw, tw, bw = _words(g["keywords"]), _words(g["title"]), _words(" ".join(g["steps"]) + " " + g["why"])
        s = 3 * len(qw & kw) + 3 * len(qw & tw) + len(qw & bw) + (2 if q.lower().strip() in g["title"].lower() else 0)
        if s:
            out.append((s, g))
    out.sort(key=lambda x: -x[0])
    top = out[0][0] if out else 0
    out = [o for o in out if o[0] * 4 >= top]
    return [{"id": g["id"], "title": g["title"], "area": g["area"], "minutes": g["minutes"], "why": g["why"], "score": s} for s, g in out[:limit]]


def for_ref(ref: str) -> str | None:
    return REF.get(ref.split(":")[0])


def areas() -> dict:
    out: dict[str, list[dict]] = {a: [] for a in AREAS}
    for g in GUIDES:
        out[g["area"]].append({"id": g["id"], "title": g["title"], "minutes": g["minutes"]})
    return out


TOOL_FIELD_FIX = {"name": "field_fix", "description": "Look up the how-to guide for a problem in computer engineering, AI engineering, ML/NLP/deep learning, project management or full stack work. action 'search': query = what the user typed (e.g. 'board resets when motor starts', 'assistant got worse', 'client adds extra work'), optional area -> best guides. "
                  "action 'guide': id -> full guide with steps, how to check it worked, time and cautions. Walk the user through one step at a time, give the caution before any risky step, and do not claim it worked until they have run the check.",
                  "input_schema": {"type": "object", "properties": {"action": {"type": "string", "enum": ["search", "guide"]}, "query": {"type": "string"}, "id": {"type": "string"}, "area": {"type": "string"}}, "required": ["action"]}}


def tool_result(args: dict) -> str:
    a = args or {}
    if a.get("action") == "guide":
        g = get(str(a.get("id") or ""))
        if not g:
            return json.dumps({"error": "No guide with that id.", "try": search(str(a.get("query") or a.get("id") or ""), None, 3)})
        return json.dumps(g)
    ar = a.get("area") if a.get("area") in AREAS else None
    return json.dumps({"results": search(str(a.get("query") or ""), ar, 5)})
