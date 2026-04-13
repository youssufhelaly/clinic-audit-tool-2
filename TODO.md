# To-Do List — Clinic Audit Tool & Business

## Future Tool Improvements (Priority Order)

### High Priority — Add to existing scoring categories
- [ ] **Meta description detection** — Check if each page has a meta description tag. Flag missing or duplicate meta descriptions. Fold into Local Relevance findings. Google uses meta descriptions for search result snippets — a missing one means Google picks random text from the page. High sales value: "when patients search for you, your Google listing shows no description."
- [ ] **Image alt text detection** — Check if images have alt attributes. Count images with and without alt text. Fold into Mobile Readiness or Local Relevance findings. Google explicitly says alt text is "quite important" for understanding images. Also an accessibility issue.
- [ ] **Google PageSpeed Insights API integration** — Add real mobile speed testing using Google's free API (25,000 requests/day). Returns actual mobile performance data: load time, largest contentful paint, cumulative layout shift, time to interactive, and a 0-100 mobile score. Requires a Google API key (free, 5 min setup via Google Cloud Console). Add after first client is landed — current speed risk indicators are sufficient for early sales conversations.

### Medium Priority — Quick checks, good for credibility
- [ ] **Sitemap detection** — Check if /sitemap.xml exists (simple HTTP HEAD request). Most small clinic sites don't have one. Easy win to offer.
- [ ] **robots.txt check** — Fetch /robots.txt and check if it exists and isn't accidentally blocking important pages. A misconfigured robots.txt can hide the entire site from Google.
- [ ] **Canonical tag detection** — Check for rel="canonical" in page head. Helps with duplicate content issues, especially on sites with www and non-www versions.
- [ ] **Heading structure check** — Verify each page has an H1 tag. Flag pages with missing H1 or multiple H1s. Not a ranking factor per Google, but a quality signal and easy to explain.

### Low Priority — Nice to have
- [ ] **Open Graph tags** — Check for og:title, og:description, og:image for social media sharing previews.
- [ ] **Favicon detection** — Google shows favicons in search results. Missing one looks unprofessional.
- [ ] **SSL certificate check** — Verify HTTPS is working properly (not just present but no mixed content warnings).

### Not Worth Adding (Google says these don't matter)
- ~~Meta keywords tag~~ — Google ignores this entirely
- ~~Keyword density~~ — Google doesn't use exact keyword counts for ranking
- ~~Heading semantic order~~ — Google says order doesn't affect ranking
- ~~Content word count minimums~~ — No magical number per Google

## Business Tasks
- [ ] Pick 10 Ottawa physio clinics, run audits, rank by score
- [ ] Prepare outreach pitch using audit findings
- [ ] Finalize business name with marketing partner
- [ ] Build mock clinic website for practice delivery run

## Completed
- [x] Phase 1 — Project cleanup
- [x] Phase 2 — Scoring rewrite + actionable findings (all 7 categories including Mobile Readiness)
- [x] Phase 2 validation — Cross-referenced all scores against real sites, bugs fixed
- [x] Report generation — Internal brief PDF auto-generated from audit
- [x] Cross-referenced auditv.py against Google SEO Starter Guide — confirmed alignment, identified gaps
