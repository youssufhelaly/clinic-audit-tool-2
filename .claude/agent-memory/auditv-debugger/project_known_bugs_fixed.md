---
name: known_bugs_fixed_in_auditv
description: Bugs confirmed and fixed in auditv.py, with root causes and fix approach
type: project
---

Bugs fixed in auditv.py as of 2026-03-25 (session against activphysio.ca):

**Bug 1: ADDRESS_PATTERN regex crashes at import (re.error: missing ), unterminated subpattern)**
- Root cause: `re.VERBOSE` mode treats `#` as a comment delimiter. The alternation `(?:suite|ste|unit|#|floor|fl)` had a bare `#` that cut off the rest of the group.
- Fix: Escaped `#` as `\#` inside the non-capturing group.
- Line: ~176 in ADDRESS_PATTERN

**Why:** VERBOSE mode ignores `#` and everything after it on the line as a comment.
**How to apply:** Any `re.VERBOSE` pattern using `#` as a literal must escape it as `\#`.

---

**Bug 2: UnicodeEncodeError on Windows — block chars █ and ░ not in cp1252**
- Root cause: Windows terminal defaults to cp1252. The scorecard bar uses `█`/`░` (U+2588/U+2591) which are outside cp1252.
- Fix: Added `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")` at module top (after imports).
- This also covers em-dash `—` in print statements.

**Why:** The script uses Unicode block characters for visual bar rendering.
**How to apply:** Always apply UTF-8 stdout reconfiguration when deploying on Windows.

---

**Bug 3: Email not detected — hidden in mailto: href attributes only**
- Root cause: `detect_contact_signals` ran EMAIL_PATTERN only against visible text. The site (activphysio.ca) displays email as `<a href="mailto:info@activphysio.ca">Email</a>` — the address is never in a text node.
- Fix: Added `raw_html` parameter to `detect_contact_signals`. When no email found in visible text, falls back to extracting from `mailto:` hrefs via regex on raw HTML. Updated `extract_page_signals` to pass `html` as `raw_html`.

**Why:** Many clinic sites put email only in href attributes for anti-spam reasons.
**How to apply:** Always consider raw HTML fallback for contact signals; visible text is not sufficient.

---

**Bug 4: Toronto false positive in location detection (find_locations)**
- Root cause: `find_locations` counted raw occurrences of city names. "University of Toronto" appeared exactly 2 times on /team page, triggering the >= 2 threshold for a real service location.
- Fix: Added `NON_LOCATION_PREFIXES` list inside `find_locations`. After counting raw occurrences, subtracts occurrences preceded by "university of ", "college of ", or "institute of " before applying threshold.

**Why:** Team bio pages often mention where therapists trained, which contains city names in educational context.
**How to apply:** Location detection needs context filtering; raw count alone is unreliable on team/bio pages.

---

**Bug 5: Priority issues showed misleading problem-framing for high scores (8-9/10)**
- Root cause: `generate_priority_issues` included all categories scoring `< 10`, so a score of 9/10 showed up as a "priority issue" with text like "Booking signals are limited or weak."
- Fix: Changed threshold to `<= PRIORITY_ISSUE_THRESHOLD` (set to 6). Only genuinely weak categories (0-6/10) are surfaced as issues. High-scoring areas (7-9) are not flagged.

**Why:** Static issue explanations are always phrased as problems; when the score is already good, showing them as issues is misleading and erodes trust in the audit.
**How to apply:** Issue generation should only surface categories that are actually below a meaningful performance threshold.

---

**Bug 6: Direct billing false positive — negated language matched as positive (2026-04-03)**
- Root cause: `assess_insurance_depth` used `any(phrase in text ...)` for `DIRECT_BILLING_PHRASES`. The phrase "bill your insurance" matched inside "we are unable to bill your insurance company directly" on vijaysharmaphysiotherapy.ca/faqs, causing the site to be scored as having direct billing when it explicitly says the opposite.
- Fix: Replaced the single-line check with a loop that scans a 60-char window before each phrase match for negation words ("unable", "cannot", "can't", "do not", etc.). Only accepts the match if no negation precedes it.
- Affected site: vijaysharmaphysiotherapy.ca scored 6 (moderate: direct billing) instead of 4 (vague: on homepage).

**Why:** Simple substring matching cannot distinguish "we offer direct billing" from "we cannot offer direct billing."
**How to apply:** Any insurance phrase match should include a backward negation window check before being accepted.

---

**Bug 7: Named insurance provider false positive — negated FAQ context (2026-04-03)**
- Root cause: `assess_insurance_depth` detected "WSIB" as a provider on activphysio.ca/faq. The FAQ says "Do you see WSIB clients? No, the clinic does not see WSIB clients." The first occurrence of "wsib" was in the question itself, before the negation ("No, ...does not see") appeared in the text. The backward window check correctly filtered the second occurrence but the first occurrence had no negation before it, so the provider was still added.
- Fix: Extended the negation check to also scan a 120-char window **after** each match. The after-window catches FAQ Q&A patterns where the provider appears in the question and the negative answer follows. Provider is only confirmed if neither the before-window nor the after-window contains a negation.
- Affected site: activphysio.ca incorrectly scored 8 (strong: direct billing + WSIB) instead of 6 (moderate: direct billing only, no named providers).

**Why:** FAQ pages often pattern as "Do you accept X? No." — the question legitimately contains the keyword but the intent is negative.
**How to apply:** For FAQ pages, provider keyword windows must check both before AND after the match position.

---

**Bug 8: Testimonial count inflation — container elements counted alongside their children (2026-04-03)**
- Root cause: `detect_trust_signals` iterated all elements with testimonial-related class/id names. A SiteOrigin Testimonials widget (class `sow-testimonials`) nests multiple divs: the outer container, a wrapper per item, and the text div per item. All match the "testimonial" keyword, so 4 real quotes produced a count of 14.
- Fix: Collect all matching elements first, then only count elements that do NOT contain any other matching element as a descendant (leaf-only count). Changed from sequential `testimonial_count += 1` to a two-pass approach: collect all, then filter out containers.
- Affected site: activphysio.ca reported 14 testimonials instead of 3.
- Score impact: None for this site (scoring doesn't use the raw count in the branch that applied here), but the count field in the output was misleading.

**Why:** Nested widget markup wraps each testimonial in multiple divs, all with "testimonial" in their class names.
**How to apply:** When counting items from class-based detection, always prefer leaf elements to avoid container double-counting.

---

**Bug 9: `YEARS_IN_PRACTICE_PHRASES` — bare "serving" phrase too generic (2026-04-03)**
- Root cause: `"serving"` was in `YEARS_IN_PRACTICE_PHRASES`. Any mention of "serving patients" or "serving your needs" would trigger `has_years_in_practice = True`, which is not an establishment date signal.
- Fix: Removed `"serving"` from the list. `"years serving"` (also in the list) is specific enough.
- Affected site: vijaysharmaphysiotherapy.ca could have triggered on generic copy; activphysio.ca correctly fires on "since 1992" and "established in 1992" without needing the bare "serving" phrase.

**Why:** A bare substring match on "serving" fires on essentially every clinic site that mentions serving clients.
**How to apply:** All YEARS_IN_PRACTICE_PHRASES must require enough context to distinguish establishment dates from generic service language.
