---
name: Booking Platform Signatures — known gaps and additions
description: Booking platforms discovered in real clinic audits that were missing from BOOKING_PLATFORM_SIGNATURES
type: project
---

Medexa (medexa.com) was added to BOOKING_PLATFORM_SIGNATURES on 2026-04-03 after medisportphysio.com scored 0/10 Booking Conversion despite having a live "Book Now" button linking to secure.medexa.com.

**Why:** BOOKING_PLATFORM_SIGNATURES only included Janeapp, Cliniko, Acuity, Calendly, GOrendezvous, Noterro, Mindbody, PhysiTrack. Medexa is used by Quebec/bilingual clinics.

**How to apply:** When a clinic scores 0 on Booking Conversion but has high booking keyword counts (>10), inspect the homepage links for unknown booking platform domains before concluding no booking exists. Add the domain to BOOKING_PLATFORM_SIGNATURES.
