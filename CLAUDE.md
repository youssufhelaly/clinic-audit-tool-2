# PROJECT: Clinic Audit Tool (auditv.py)

## What This Project Is

A Python-based website audit tool built for a real business.

The business helps physiotherapy clinics grow by improving their online presence — specifically their ability to get found, get chosen, and get booked. This tool is the backbone of that business. It analyzes clinic websites, identifies what is costing them patients, and produces insights the operator uses in sales conversations with clinic owners.

This is NOT a generic scraper or SEO checker.
This is a **sales-focused audit system** where every output must be accurate enough to say to a clinic owner's face.

---

## Business Context

The operator:
- Has direct experience working inside physiotherapy clinics (former physio assistant / rehab assistant)
- Is based in Ottawa, Ontario — targeting privately owned physio clinics in the Ottawa-Gatineau area first
- Is pre-revenue, working toward landing the first paying client
- Uses this tool internally to identify weaknesses before reaching out to clinics
- Does NOT show this tool to clinic owners — it's for preparation only

The operator's edge is clinical knowledge + the ability to spot real problems that generic marketers miss.

Everything this tool produces must support one question: **"What would I say to this clinic owner to show them I understand their problem?"**

---

## Current State

- Single-file script: `auditv.py`
- CLI-based, takes a URL as input
- Crawls key pages (homepage, services, contact, about, team, FAQ, booking)
- Extracts signals: location, services, booking, reviews, contact info, insurance
- Outputs: summary, scorecard (/70), priority issues, page-level signals, JSON export
- Has been tested against 4 real Ottawa-area clinics
- Debugger agent (`auditv-debugger`) handles testing and bug fixes

---

## Core Philosophy

### 1. Score quality, not just presence
The biggest flaw in the current system is that it counts *whether something exists* but not *how well it's done*. A contact form is not the same as online booking. The word "insurance" appearing once is not the same as listing providers and explaining direct billing.

Every scoring category must distinguish between:
- **Not present** (0-2)
- **Present but weak** (3-5)
- **Present and adequate** (6-7)
- **Present and strong** (8-10)

### 2. Real-world accuracy > theoretical completeness
The tool must reflect how a **real patient searching Google** would experience the site.

Avoid:
- naive keyword matching that inflates scores
- counting weak signals as strong ones
- false positives (e.g., "University of Toronto" as a location)
- giving high scores for vague or buried information

### 3. Signal quality > signal quantity
Not all detections are equal.

Stronger signals (weight heavily):
- homepage content
- services page content
- title tags and H1 headings
- dedicated booking/contact pages

Weaker signals (weight lightly or flag):
- footer-only mentions
- team bios
- FAQ pages
- deeply buried inner pages

### 4. Every score must be explainable
If the tool gives a 7/10, there must be a clear list of what earned those points and what's missing. Generic explanations like "signals appear limited" are not acceptable. The output must say specifically what was found, where, and what's lacking.

### 5. Minimal, targeted changes
When modifying code:
- do NOT rewrite the entire script unless structurally necessary
- fix root causes, not symptoms
- preserve working logic
- avoid over-engineering
- every change must be testable against real clinic sites

### 6. Iterative testing is mandatory
Every change must:
1. Run on at least 2 real clinic sites
2. Be verified against actual website content (manually check what the site shows)
3. Produce consistent, accurate output across multiple runs

---

## Scoring Model

Categories (all /10):
- **Local Relevance** — Can patients in the area find this clinic through local search?
- **Services Visibility** — Can a visitor quickly understand what the clinic offers?
- **Booking Conversion** — How easy is it for a patient to actually book an appointment?
- **Trust / Reviews** — Does the site build confidence through social proof?
- **Contact Completeness** — Can patients easily reach the clinic?
- **Insurance / Accessibility** — Is billing/insurance information clear and helpful?
- **Mobile Readiness** — Is the site usable on a phone? Does booking work on mobile?

Total: /70

### Scoring Rules
- Scores must reflect quality tiers, not just keyword counts
- Each score must come with specific findings (what was detected, where, what's missing)
- Priority issues are only flagged for scores <= 6
- High scores (7+) should genuinely mean the site does that thing well

---

## Known Problems Being Fixed

### Booking scores too generous
- Current logic counts booking-related keywords and gives 7/10 for 2 mentions on homepage
- Does NOT distinguish between a contact form (weak) and real online booking (strong)
- Must detect: booking platform (Janeapp, Cliniko, etc.) vs. contact form vs. phone-only vs. nothing

### Insurance scores too generous
- Current logic gives 9/10 if any insurance keyword appears on a key page
- Does NOT check whether providers are named, direct billing is offered, or information is actionable
- A vague "yes we accept insurance" should score much lower than a detailed billing page

### Services scoring ignores presentation quality
- Current logic only counts how many service categories are detected
- Does NOT check whether services are explained, have dedicated pages, or are clearly presented
- A list of service names with no descriptions should score lower than detailed service pages

### Local relevance scoring is too simple
- Gives points for city name + address existing, but doesn't check local SEO structure
- Should evaluate: city in title tag, neighbourhood mentions, service-area pages, schema markup

### No actionable findings in output
- Current priority issues use canned generic explanations
- Must be replaced with specific findings from the actual site analysis

---

## Project Structure

```
CLINIC-AUDIT-TOOL/
├── .claude/
│   └── settings_local.json
├── agents/
│   └── auditv-debugger.md
├── agent-memory/
│   └── auditv-debugger/
│       ├── MEMORY.md
│       └── project_known_bugs_fixed.md
├── commands/
│   └── run-audit.md
├── outputs/
│   └── audit_output_*.json
├── auditv.py
└── CLAUDE.md
```

Every file has a purpose. Do not create files or folders that don't serve the system.

---

## Improvement Roadmap

### Phase 1 — Project cleanup ✅ DONE
Removed dead files, empty agent folders, old script versions.

### Phase 2 — Scoring rewrite + actionable findings ✅ DONE
All 6 scoring categories rewritten with quality-based tiers. Validated against 4 real clinics.
- All categories now grade quality, not just keyword presence
- Every score includes specific findings explaining what was found and what's missing
- New detection functions: `detect_booking_system`, `assess_insurance_depth`, `assess_service_presentation`, `detect_map_embed`, `detect_schema_markup`, `detect_trust_signals`, `detect_contact_quality`
- www vs. non-www URL deduplication fixed
- Validated final scores: vijay 26/60, activ 43/60, ocp 34/60, medisport 33/60

### Phase 3 — Google review and social proof detection
- Detect embedded Google review widgets, testimonial sections, star ratings
- Check for links to Google Business Profile
- Distinguish between real review integration vs. just mentioning "reviews"

### Phase 4 — Output cleanup for client-readiness
- Restructure output so findings could be pasted into an email or pitch
- Add "what we'd recommend" summary section
- Clean up JSON structure for future report generation

### Phase 5 — Competitor comparison
- Run audits on multiple clinics in same area
- Produce simple comparison output
- "Your clinic scores X, top competitor scores Y, here's where you're losing"

### Phase 6 — Clinic discovery and lead pipeline
- Find clinics automatically (Google Maps, directories)
- Score and rank them as leads
- Prioritize by opportunity size (low score = high opportunity)

**Current focus: Phase 3. Phase 2 is complete and verified.**

---

## Agent Usage

### auditv-debugger
Used for:
- Running the script against real clinic websites
- Reproducing and fixing bugs
- **Verifying score accuracy** — fetch the actual website independently, check what it shows, compare against what auditv.py scored, flag discrepancies
- Testing changes across multiple clinic sites

Must:
- Test against live websites
- Cross-reference scores against real page content
- Iterate until output is stable and accurate
- Avoid over-fixing

---

## Rules for Claude

- Do NOT overcomplicate solutions
- Do NOT suggest full rewrites unless structurally necessary
- Always tie changes to real output accuracy
- Prefer practical fixes over theoretical improvements
- Keep responses concise and actionable
- Every scoring change must be tested against real clinic sites
- If a score doesn't match what a human would judge by looking at the site, the score is wrong
- When in doubt, ask: "Would this output help the operator have a credible conversation with a clinic owner?"
