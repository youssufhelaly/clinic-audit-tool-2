"""
generate_reports.py — Convert audit JSON into two outputs:
1. Internal Brief (Markdown) — for your marketing partner
2. Client-Facing PDF — for the clinic owner

Usage:
  python generate_reports.py audit_output_vijaysharmaphysiotherapy_ca.json
"""

import json
import sys
import os
from datetime import datetime

# ---------------------------------------------------------------------------
# SCORE LABELS — no raw numbers for the client
# ---------------------------------------------------------------------------
def score_label(score):
    if score <= 2:
        return "Needs Immediate Attention"
    elif score <= 4:
        return "Needs Improvement"
    elif score <= 6:
        return "Moderate"
    elif score <= 8:
        return "Good"
    else:
        return "Strong"

def score_color_rgb(score):
    """Return RGB tuple for reportlab based on score."""
    if score <= 2:
        return (0.8, 0.15, 0.15)
    elif score <= 4:
        return (0.85, 0.45, 0.1)
    elif score <= 6:
        return (0.8, 0.7, 0.1)
    elif score <= 8:
        return (0.2, 0.65, 0.3)
    else:
        return (0.1, 0.5, 0.2)

# ---------------------------------------------------------------------------
# 1. INTERNAL BRIEF (Markdown) — for your marketing partner
# ---------------------------------------------------------------------------
def generate_internal_brief(data, output_path):
    scores = data["scores"]["categories"]
    findings = data["scores"]["findings"]
    agg = data["aggregated_signals"]
    
    lines = []
    lines.append(f"# Internal Audit Brief — {data['business_name']}")
    lines.append(f"**URL:** {data['url']}")
    lines.append(f"**Date:** {datetime.now().strftime('%B %d, %Y')}")
    lines.append(f"**Overall Score:** {data['scores']['total']}/{data['scores']['max']}")
    lines.append("")
    
    # Quick scorecard
    lines.append("## Scorecard")
    lines.append("")
    for cat, score in scores.items():
        label = score_label(score)
        lines.append(f"- **{cat}:** {score}/10 — {label}")
    lines.append("")
    
    # Priority issues — what to build the pitch around
    lines.append("## Top Issues (Build the Pitch Around These)")
    lines.append("")
    for issue in data["priority_issues"]:
        lines.append(f"### {issue['category']} — {issue['score']}/{issue['max']}")
        for f in issue["findings"]:
            lines.append(f"- {f}")
        lines.append("")
    
    # What's working — don't pitch fixing things that aren't broken
    lines.append("## What's Working (Don't Pitch These)")
    lines.append("")
    for cat, score in scores.items():
        if score >= 7:
            lines.append(f"- **{cat}** ({score}/10): {'; '.join(findings.get(cat, []))}")
    lines.append("")
    
    # Key facts for the conversation
    lines.append("## Key Facts for the Conversation")
    lines.append("")
    lines.append(f"- **Booking system:** {agg.get('booking_system_type', 'unknown')} {'(' + agg['booking_platform_name'] + ')' if agg.get('booking_platform_name') else ''}")
    lines.append(f"- **Insurance info:** {agg.get('insurance_specificity', 'unknown')} — providers named: {', '.join(agg.get('insurance_providers_found', [])) or 'none'}")
    lines.append(f"- **Direct billing mentioned:** {'Yes' if agg.get('direct_billing_mentioned') else 'No'}")
    lines.append(f"- **Reviews/testimonials on site:** {'Yes' if agg.get('has_testimonial_content') or agg.get('has_review_widget') else 'None'}")
    lines.append(f"- **Google Maps on contact page:** {'Yes' if agg.get('google_map_on_contact') else 'No'}")
    lines.append(f"- **Services page exists:** {'Yes' if agg.get('service_presentation', {}).get('has_services_page') else 'No'}")
    lines.append(f"- **Pages analyzed:** {len(data.get('pages_analyzed', []))}")
    lines.append("")
    
    # Suggested package
    lines.append("## Suggested Package to Offer")
    lines.append("")
    for issue in data["priority_issues"]:
        cat = issue["category"]
        if cat == "Trust / Reviews":
            lines.append("- **Add reviews/testimonials:** Embed Google reviews on homepage, add testimonial section, link to Google Business Profile")
        elif cat == "Booking Conversion":
            if agg.get("booking_system_type") == "form":
                lines.append("- **Online booking setup:** Replace contact form with real-time booking (Janeapp, Cliniko, etc.) so patients can book directly")
            else:
                lines.append("- **Improve booking flow:** Make booking CTA more prominent, add dedicated booking page")
        elif cat == "Services Visibility":
            lines.append("- **Services page creation/redesign:** Build a proper services page with descriptions for each service, add dedicated sub-pages for key services")
        elif cat == "Insurance / Accessibility":
            lines.append("- **Insurance clarity:** Add specific provider names, explain direct billing process, make insurance info prominent on homepage")
        elif cat == "Local Relevance":
            lines.append("- **Local SEO improvements:** Add Google Map embed, add LocalBusiness schema, create service area content")
    lines.append("")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"  Internal brief saved: {output_path}")


# ---------------------------------------------------------------------------
# 2. CLIENT-FACING PDF — for the clinic owner
# ---------------------------------------------------------------------------
def generate_client_pdf(data, output_path):
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib.colors import HexColor, Color
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER

    scores = data["scores"]["categories"]
    findings = data["scores"]["findings"]
    
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        topMargin=0.6*inch,
        bottomMargin=0.6*inch,
        leftMargin=0.75*inch,
        rightMargin=0.75*inch,
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    styles.add(ParagraphStyle(
        name="ReportTitle",
        parent=styles["Title"],
        fontSize=22,
        textColor=HexColor("#1a1a2e"),
        spaceAfter=4,
        alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="ReportSubtitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=HexColor("#555555"),
        spaceAfter=16,
    ))
    styles.add(ParagraphStyle(
        name="SectionHead",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=HexColor("#1a1a2e"),
        spaceBefore=18,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="Finding",
        parent=styles["Normal"],
        fontSize=10,
        textColor=HexColor("#333333"),
        leftIndent=12,
        spaceAfter=4,
        leading=14,
    ))
    styles.add(ParagraphStyle(
        name="CategoryName",
        parent=styles["Normal"],
        fontSize=11,
        textColor=HexColor("#1a1a2e"),
        leading=14,
    ))
    styles.add(ParagraphStyle(
        name="FooterText",
        parent=styles["Normal"],
        fontSize=8,
        textColor=HexColor("#999999"),
        alignment=TA_CENTER,
    ))
    
    story = []
    
    # --- HEADER ---
    story.append(Paragraph("Website Performance Review", styles["ReportTitle"]))
    story.append(Paragraph(
        f"{data['business_name']}  |  {data['url']}  |  {datetime.now().strftime('%B %d, %Y')}",
        styles["ReportSubtitle"]
    ))
    story.append(HRFlowable(width="100%", thickness=1.5, color=HexColor("#1a1a2e")))
    story.append(Spacer(1, 12))
    
    # --- OVERVIEW ---
    story.append(Paragraph("Overview", styles["SectionHead"]))
    total = data["scores"]["total"]
    max_score = data["scores"]["max"]
    pct = round((total / max_score) * 100)
    
    overview_text = (
        f"We reviewed your website across 6 key areas that directly impact whether patients "
        f"find your clinic, trust it, and book an appointment. "
        f"Your site scored <b>{total} out of {max_score}</b> ({pct}%). "
        f"Below is a summary of what we found."
    )
    story.append(Paragraph(overview_text, styles["Normal"]))
    story.append(Spacer(1, 14))
    
    # --- SCORECARD TABLE ---
    story.append(Paragraph("Performance Summary", styles["SectionHead"]))
    
    table_data = [["Area", "Status", ""]]
    for cat, score in scores.items():
        label = score_label(score)
        r, g, b = score_color_rgb(score)
        # Build a colored block as visual indicator
        table_data.append([cat, label, f"{score}/10"])
    
    t = Table(table_data, colWidths=[2.8*inch, 2.2*inch, 0.8*inch])
    
    # Build style commands
    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 10),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("ALIGN", (2, 0), (2, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#dddddd")),
    ]
    
    # Color-code each status cell
    for i, (cat, score) in enumerate(scores.items(), start=1):
        r, g, b = score_color_rgb(score)
        style_commands.append(("TEXTCOLOR", (1, i), (1, i), Color(r, g, b)))
        style_commands.append(("FONTNAME", (1, i), (1, i), "Helvetica-Bold"))
    
    # Alternate row shading
    for i in range(1, len(table_data)):
        if i % 2 == 0:
            style_commands.append(("BACKGROUND", (0, i), (-1, i), HexColor("#f8f8f8")))
    
    t.setStyle(TableStyle(style_commands))
    story.append(t)
    story.append(Spacer(1, 16))
    
    # --- KEY FINDINGS ---
    story.append(Paragraph("Key Findings", styles["SectionHead"]))
    
    # Only show categories that need attention (score <= 6)
    weak_cats = [(cat, score) for cat, score in scores.items() if score <= 6]
    weak_cats.sort(key=lambda x: x[1])
    
    for cat, score in weak_cats:
        label = score_label(score)
        r, g, b = score_color_rgb(score)
        story.append(Paragraph(
            f"<b>{cat}</b> — <font color='#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}'>{label}</font>",
            styles["CategoryName"]
        ))
        cat_findings = findings.get(cat, [])
        for f in cat_findings:
            story.append(Paragraph(f"- {f}", styles["Finding"]))
        story.append(Spacer(1, 8))
    
    # --- WHAT'S WORKING ---
    strong_cats = [(cat, score) for cat, score in scores.items() if score > 6]
    if strong_cats:
        story.append(Paragraph("What's Working Well", styles["SectionHead"]))
        for cat, score in strong_cats:
            cat_findings = findings.get(cat, [])
            summary = "; ".join(cat_findings[:2]) if cat_findings else "Performing well."
            story.append(Paragraph(f"<b>{cat}</b> — {summary}", styles["Finding"]))
        story.append(Spacer(1, 12))
    
    # --- RECOMMENDED NEXT STEPS ---
    story.append(Paragraph("Recommended Next Steps", styles["SectionHead"]))
    
    step_num = 1
    agg = data["aggregated_signals"]
    
    for cat, score in weak_cats:
        if cat == "Trust / Reviews":
            story.append(Paragraph(
                f"<b>{step_num}. Add patient reviews and testimonials to your website.</b> "
                f"New patients look for social proof before booking. Adding Google reviews "
                f"to your homepage builds immediate trust.",
                styles["Finding"]
            ))
            step_num += 1
        elif cat == "Booking Conversion":
            if agg.get("booking_system_type") == "form":
                story.append(Paragraph(
                    f"<b>{step_num}. Enable online booking so patients can schedule directly.</b> "
                    f"Right now, patients fill out a form and wait to hear back. "
                    f"A real-time booking system lets them pick a time and confirm instantly.",
                    styles["Finding"]
                ))
            else:
                story.append(Paragraph(
                    f"<b>{step_num}. Make your booking button easier to find.</b> "
                    f"Patients should be able to book from any page on your site with one click.",
                    styles["Finding"]
                ))
            step_num += 1
        elif cat == "Services Visibility":
            story.append(Paragraph(
                f"<b>{step_num}. Create a dedicated services page with clear descriptions.</b> "
                f"Patients should immediately understand what you offer and whether "
                f"you can help with their specific issue.",
                styles["Finding"]
            ))
            step_num += 1
        elif cat == "Insurance / Accessibility":
            story.append(Paragraph(
                f"<b>{step_num}. Clarify your insurance and billing information.</b> "
                f"Many patients filter clinics by whether their insurance is accepted. "
                f"Listing specific providers and explaining direct billing removes a major barrier.",
                styles["Finding"]
            ))
            step_num += 1
        elif cat == "Local Relevance":
            story.append(Paragraph(
                f"<b>{step_num}. Strengthen your local search presence.</b> "
                f"Adding a Google Map to your contact page and optimizing your site structure "
                f"helps patients in your area find you more easily.",
                styles["Finding"]
            ))
            step_num += 1
    
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#cccccc")))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"This review was prepared on {datetime.now().strftime('%B %d, %Y')}. "
        f"Results are based on an analysis of {len(data.get('pages_analyzed', []))} pages on your website.",
        styles["FooterText"]
    ))
    
    doc.build(story)
    print(f"  Client PDF saved: {output_path}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_reports.py <audit_output.json>")
        sys.exit(1)
    
    json_path = sys.argv[1]
    
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Build output filenames from domain
    domain = data["url"].split("//")[-1].split("/")[0].lstrip("www.").replace(".", "_")
    
    brief_path = f"brief_{domain}.md"
    pdf_path = f"report_{domain}.pdf"
    
    print(f"\nGenerating reports for: {data['business_name']}")
    print(f"  Source: {json_path}")
    print()
    
    generate_internal_brief(data, brief_path)
    generate_client_pdf(data, pdf_path)
    
    print("\nDone.")


if __name__ == "__main__":
    main()
