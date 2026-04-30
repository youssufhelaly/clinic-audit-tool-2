# Clinic Website Audit Tool

A Python-based website audit system for analyzing physiotherapy clinic websites and identifying opportunities to improve patient acquisition.

## What This Tool Does

The audit analyzes clinic websites across **6 key categories** (/70 total):

1. **Local Relevance** — Can patients find you on Google?
2. **Services Visibility** — Can patients understand what you offer?
3. **Booking Conversion** — How easy is it to book?
4. **Trust / Reviews** — Do new patients trust you?
5. **Contact Completeness** — Can patients reach you?
6. **Insurance / Accessibility** — Is insurance info clear?
7. **Mobile Readiness** — Does it work on phones?

Outputs include:
- **Terminal report** — Immediate feedback with scores and findings
- **JSON export** — Full data for analysis and comparison
- **Internal brief** (Markdown) — For your sales team
- **Client PDF** — Professional report for clinic owners

## Quick Start

### 1. Setup (First Time)

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install requests beautifulsoup4 reportlab
```

### 2. Run an Audit

**Option A: Interactive**
```bash
python3 auditv.py
# Enter URL when prompted
```

**Option B: With automatic report generation**
```bash
./run_audit_and_report.sh https://www.example-physio.com
```

**Option C: Generate reports from existing audit**
```bash
python3 generate_reports.py outputs/audit_output_*.json
```

## Output Files

After running an audit on `https://www.example-physio.com`:

- `outputs/audit_output_examplephysio_com.json` — Raw data (full analysis)
- `brief_examplephysio_com.md` — Internal brief (for your team)
- `report_examplephysio_com.pdf` — Client-facing PDF (for clinic owner)

## How to Use Outputs

### Internal Brief (Markdown)
Read this before calling the clinic. It includes:
- Scorecard with all 6 categories
- Top issues (what to build your pitch around)
- What's working well (don't pitch fixing these)
- Key facts for the conversation (booking system, insurance info, reviews, etc.)
- Suggested service packages to offer

### Client PDF
Send or present this to the clinic owner. It shows:
- Performance summary with color-coded scores
- Key findings for weak areas
- What's working well
- Recommended next steps

### JSON Data
Use this for analysis, comparison, or building custom reports. Contains:
- All detected signals (testimonials, booking system, reviews, services, etc.)
- Score explanations
- Priority issues with specific findings

## How Scoring Works

Each category is graded on a **quality tier system** (not just keyword counts):

- **0-2/10:** Critical problem
- **3-4/10:** Needs improvement
- **5-6/10:** Moderate / average
- **7-8/10:** Good
- **9-10/10:** Strong / excellent

**Example:**
- Contact form only = 3/10 booking score (weak)
- Real online booking (Janeapp, Cliniko) = 8/10 booking score (strong)
- No reviews + no testimonials = 0/10 trust score
- Professional credentials + years in practice = minimum 2/10 trust score

## Examples

### Scenario: Low Booking Score
```
Booking Conversion: 3/10 — Critical
- Contact form only, no online booking available
- Make recommendation: Add Janeapp or Cliniko for real-time booking
```

### Scenario: Low Trust Score
```
Trust / Reviews: 2/10 — Critical
- No testimonials or reviews visible
- Professional credentials detected — reinforces trust
- Make recommendation: Embed Google Business Profile, add 3-4 testimonials
```

### Scenario: Services Visibility
```
Services Visibility: 4/10 — Needs Improvement
- Services listed but no descriptions or dedicated pages
- Make recommendation: Create service page with descriptions for each service
```

## Project Structure

```
clinic-audit-tool/
├── .venv/                      (virtual environment — auto-created)
├── auditv.py                   (main audit script)
├── generate_reports.py         (convert JSON to reports)
├── run_audit_and_report.sh     (convenience script)
├── SALES_GUIDE.md              (sales pitch framework)
├── outputs/                    (generated JSON audits)
├── brief_*.md                  (generated internal briefs)
├── report_*.pdf                (generated client PDFs)
└── CLAUDE.md                   (project development notes)
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'requests'"
```bash
source .venv/bin/activate
pip install requests beautifulsoup4 reportlab
```

### "Can't find Python" or "python not found"
Use `python3` instead of `python`:
```bash
python3 auditv.py
```

### Audit is slow or timing out
Some sites have slow hosting. The tool has automatic retries and timeouts (30 seconds per page). If a site consistently fails, check if it's down or blocking bots.

## Next Steps

1. **Run audits on target clinics** in your market
2. **Use internal briefs** to prepare your sales conversations
3. **Send client PDFs** to clinics you're pitching
4. **Track patterns** — which issues are most common? (tells you where to focus your pitch)

---

For sales guidance on using these reports with clinic owners, see `SALES_GUIDE.md`.
