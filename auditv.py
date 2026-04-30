"""
auditv.py — Clinic Website Audit Tool (v1)
==========================================
Single-file CLI tool for auditing physiotherapy / rehab clinic websites.
Designed for lead generation and future agent automation.

Future extensions (not built yet):
  - bulk clinic audits
  - lead ranking / competitor comparison
  - CRM / spreadsheet export
  - agent-driven orchestration

Usage:
  python auditv.py
"""

import re
import json
import sys
import io
import os
from datetime import datetime
from urllib.parse import urlparse, urljoin, urlunparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# Force UTF-8 output so Unicode bar/dash chars render correctly on all platforms
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import requests
import urllib3
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Suppress SSL warnings — development/testing only, NOT for production use
# ---------------------------------------------------------------------------
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# REQUEST DEFAULTS
# ---------------------------------------------------------------------------
REQUEST_TIMEOUT = 20  # Increased to 20s for slower pages or rate-limited responses
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ClinicAuditor/1.0; +https://example.com)"
    )
}

# ---------------------------------------------------------------------------
# RELEVANT PATH SEEDS — always check these if they exist on the domain
# ---------------------------------------------------------------------------
SEED_PATHS = [
    "/services",
    "/treatments",
    "/conditions",
    "/contact",
    "/about",
    "/team",
    "/book",
    "/booking",
    "/appointment",
    "/faq",
    "/reviews",
    "/testimonials",
]

# Keywords that make an internal link "relevant" enough to include in crawl
RELEVANT_LINK_WORDS = {
    "service", "contact", "about", "team", "book", "booking",
    "appointment", "faq", "treatment", "physio", "condition", "therapy",
    "schedule", "reserve", "testimonial", "review", "specialist", "doctor",
    "clinic", "center", "staff", "provider", "patient", "hour",
}

# Paths to skip even if they contain relevant words (noise exclusions)
SKIP_PATH_FRAGMENTS = {
    "blog", "privacy", "legal", "careers", "sitemap", "wp-admin",
    "login", "register", "cart", "checkout", "tag", "category",
}

# ---------------------------------------------------------------------------
# CANADIAN CITIES (representative — add more as needed)
# ---------------------------------------------------------------------------
CANADIAN_CITIES = [
    "toronto", "ottawa", "montreal", "calgary", "edmonton", "vancouver",
    "mississauga", "brampton", "hamilton", "london", "markham", "vaughan",
    "kitchener", "windsor", "saskatoon", "regina", "richmond hill",
    "richmond", "burnaby", "surrey", "kelowna", "abbotsford", "victoria",
    "halifax", "fredericton", "moncton", "saint john", "charlottetown",
    "st. john's", "whitehorse", "yellowknife", "iqaluit", "kanata",
    "nepean", "gloucester", "barrhaven", "orleans", "gatineau", "laval",
    "longueuil", "sherbrooke", "levis", "saguenay", "trois-rivieres",
    "oakville", "burlington", "oshawa", "ajax", "pickering", "whitby",
    "newmarket", "aurora", "barrie", "sudbury", "thunder bay", "guelph",
    "cambridge", "waterloo", "st. catharines", "niagara falls",
    "peterborough", "kingston", "chatham", "sarnia", "north bay",
    "lethbridge", "red deer", "medicine hat", "grande prairie",
    "fort mcmurray", "prince george", "kamloops", "nanaimo", "chilliwack",
]

# ---------------------------------------------------------------------------
# NEIGHBOURHOOD / AREA TERMS — signals sub-city local targeting
# Generic qualifiers + Ottawa-area neighbourhoods (expand as needed)
# ---------------------------------------------------------------------------
NEIGHBOURHOOD_TERMS = [
    # Generic area qualifiers
    "downtown", "uptown", "midtown", "west end", "east end",
    "north end", "south end",
    # Ottawa neighbourhoods
    "centretown", "westboro", "glebe", "hintonburg", "vanier",
    "rockcliffe", "manor park", "alta vista", "overbrook",
    "byward market", "little italy", "sandy hill", "new edinburgh",
    "lindenlea", "old ottawa south", "old ottawa east",
    # Gatineau / Outaouais
    "hull", "aylmer", "gatineau",
]

# ---------------------------------------------------------------------------
# SERVICE CATEGORIES — each maps to a list of trigger keywords
# ---------------------------------------------------------------------------
SERVICE_CATEGORIES = {
    "Physiotherapy": [
        "physiotherapy", "physiotherapist", "physio", "physical therapy",
        "physical therapist",
    ],
    "Massage Therapy": [
        "massage therapy", "massage therapist", "rmt", "therapeutic massage",
        "deep tissue", "swedish massage",
    ],
    "Chiropractic": [
        "chiropractic", "chiropractor", "chiro", "spinal adjustment",
        "spinal manipulation",
    ],
    "Acupuncture": [
        "acupuncture", "acupuncturist", "traditional chinese medicine",
        "tcm", "dry needling",
    ],
    "Manual Therapy": [
        "manual therapy", "joint mobilization", "mobilization",
        "manipulation", "myofascial",
    ],
    "Sports Rehab": [
        "sports rehab", "sports rehabilitation", "sports injury",
        "athletic therapy", "concussion", "return to sport",
    ],
    "Pelvic Health": [
        "pelvic health", "pelvic floor", "pelvic physiotherapy",
        "women's health", "pre-natal", "post-natal", "incontinence",
    ],
    "Pain Treatment": [
        "chronic pain", "back pain", "neck pain", "pain management",
        "pain relief", "shockwave", "ifc", "tens",
    ],
    "Orthotics & Support": [
        "orthotics", "custom orthotics", "bracing", "compression",
        "foot care", "insoles",
    ],
    "Wellness / Other": [
        "wellness", "rehabilitation", "rehab", "occupational therapy",
        "kinesiology", "kinesiologist", "dietitian", "naturopath",
        "yoga", "pilates",
    ],
}

# ---------------------------------------------------------------------------
# BOOKING SIGNAL KEYWORDS (multi-word phrases preferred for precision)
# ---------------------------------------------------------------------------
BOOKING_KEYWORDS = [
    "book online", "online booking", "schedule appointment",
    "request an appointment", "book now", "book a session",
    "book an appointment", "make an appointment", "schedule a visit",
    "book a visit", "schedule online", "request appointment",
    "book your appointment", "book today",
]

# ---------------------------------------------------------------------------
# BOOKING PLATFORM SIGNATURES — domains found in href/src/action attributes
# ---------------------------------------------------------------------------
BOOKING_PLATFORM_SIGNATURES = {
    "Janeapp": ["jane.app", "janeapp.com"],
    "Cliniko": ["cliniko.com"],
    "Acuity": ["acuityscheduling.com"],
    "Calendly": ["calendly.com"],
    "GOrendezvous": ["gorendezvous.com"],
    "Noterro": ["noterro.com"],
    "Mindbody": ["mindbodyonline.com", "mindbody.io"],
    "PhysiTrack": ["physitrack.com"],
    "Medexa": ["medexa.com"],
    "Juvono": ["juvono.com", "juvono.co"],
}

# Phrases indicating patients must call to book (phone-only friction)
CALL_TO_BOOK_PHRASES = [
    "call to book", "call us to book", "call to schedule",
    "phone to book", "to book, call", "to schedule, call",
    "call for an appointment", "call us for an appointment",
    "book by phone", "booking by phone",
]

# ---------------------------------------------------------------------------
# REVIEW / TRUST SIGNAL KEYWORDS
# ---------------------------------------------------------------------------
REVIEW_KEYWORDS = [
    "testimonial", "testimonials", "google review", "google reviews",
    "what people say", "what our patients say", "what our clients say",
    "patient feedback", "client feedback", "rated", "stars",
    "★★★★★", "5 star", "5-star", "read our reviews", "see our reviews",
    "patient stories",
]

# ---------------------------------------------------------------------------
# REVIEW WIDGET SIGNATURES — third-party review aggregator embed domains
# ---------------------------------------------------------------------------
REVIEW_WIDGET_SIGNATURES = [
    "elfsight.com", "embedsocial.com", "reviewshake.com", "grade.us",
    "birdeye.com", "podium.com", "trustindex.io", "widewail.com",
    "reviewtrackers.com", "rize.io",
]

# Review platform link domains and their display names
REVIEW_PLATFORM_DOMAINS = {
    "Google Business": ["google.com/maps", "g.page", "maps.app.goo"],
    "Facebook":        ["facebook.com", "fb.com"],
    "Instagram":       ["instagram.com"],
    "Yelp":            ["yelp.com", "yelp.ca"],
    "RateMDs":         ["ratemds.com"],
    "Healthgrades":    ["healthgrades.com"],
    "RateABiz":        ["rateabiz.com"],
    "Waze":            ["waze.com"],
    "ProvenExpert":    ["provenexpert.com"],
}

# Credential terms that appear in team bios / about pages
CREDENTIAL_TERMS = [
    "registered physiotherapist",
    "registered massage therapist",
    "registered kinesiologist",
    "registered acupuncturist",
    "certified athletic therapist",
    "physiotherapy resident",
    "r.pt.", "r.m.t.", "r.kin.", "r.ac.", "cat(c)",
]

# Professional association mentions
PROFESSIONAL_ASSOC_TERMS = [
    "college of physiotherapists",
    "physiotherapy ontario",
    "ontario physiotherapy association",
    "canadian physiotherapy association",
    "physiotherapy canada",
    "ontario massage therapist",
    "registered massage therapists of ontario",
]

# Language indicating years in practice or establishment date
YEARS_IN_PRACTICE_PHRASES = [
    "established in", "est. 1", "est. 2",
    "since 19", "since 20",
    "years of experience", "years in practice",
    "in practice since", "years serving",
    "founded in", "opened in",
]

# ---------------------------------------------------------------------------
# INSURANCE / DIRECT BILLING KEYWORDS
# ---------------------------------------------------------------------------
INSURANCE_KEYWORDS = [
    "insurance", "direct bill", "direct billing", "benefits",
    "extended health", "wsib", "blue cross", "sun life", "manulife",
    "greenshield", "desjardins", "claim",
]

# Named insurance providers — presence of any = specificity upgrade from vague → moderate/strong
INSURANCE_PROVIDERS = {
    "Sun Life":         ["sun life"],
    "Manulife":         ["manulife"],
    "Blue Cross":       ["blue cross"],
    "Great-West Life":  ["great-west life", "great west life", "canada life"],
    "Green Shield":     ["green shield", "greenshield"],
    "Desjardins":       ["desjardins"],
    "WSIB":             ["wsib"],
    "Veterans Affairs": ["veterans affairs", "veteran affairs"],
    "RCMP":             ["rcmp"],
}

# Explicit direct billing phrases — much stronger than just "insurance"
DIRECT_BILLING_PHRASES = [
    "direct bill", "direct billing", "we bill directly", "bill directly",
    "direct insurance billing", "bill your insurance", "billed directly",
]

# ---------------------------------------------------------------------------
# ADDRESS-LIKE PATTERNS (street-level signals)
# ---------------------------------------------------------------------------
# Matches things like "123 Main St", "Suite 200", "Unit 5", "3rd Floor"
ADDRESS_PATTERN = re.compile(
    r"""
    (
        \d{1,5}\s+[A-Za-z][A-Za-z\s\-\'\.]{2,40}   # "123 Elm Street"
        (?:street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|
           crescent|cres|court|ct|way|lane|ln|place|pl|trail|terrace)
        |
        (?:suite|ste|unit|\#|floor|fl)\s*[\d\w\-]+   # "Suite 200", "Unit 5"
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Hours of operation detection — heading phrases and day-name presence
HOURS_KEYWORDS = [
    "hours of operation", "clinic hours", "office hours", "business hours",
    "opening hours", "our hours",
]
# Day names used as a secondary signal (combined with time pattern)
_DAYS_OF_WEEK = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_TIME_PATTERN = re.compile(r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b", re.IGNORECASE)

PHONE_PATTERN = re.compile(
    r"""
    (?:\+?1[\s\-.]?)?          # optional country code
    \(?[0-9]{3}\)?[\s\-.]?     # area code
    [0-9]{3}[\s\-.]?           # first 3 digits
    [0-9]{4}                   # last 4 digits
    """,
    re.VERBOSE,
)

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


# ===========================================================================
# URL UTILITIES
# ===========================================================================

def normalize_url(url: str, base: str = "") -> str:
    """
    Normalize a URL: strip query strings, fragments, and trailing slashes.
    Resolve relative URLs against base if provided.
    Strip leading 'www.' from netloc so that www and non-www variants
    deduplicate correctly in the candidates set.
    """
    if base:
        url = urljoin(base, url)
    parsed = urlparse(url)
    # Strip www. prefix so ocphysio.com and www.ocphysio.com collapse to the same URL
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    # rebuild without query/fragment, strip trailing slash from path
    path = parsed.path.rstrip("/") or "/"
    normalized = urlunparse((parsed.scheme, netloc, path, "", "", ""))
    return normalized


def same_domain(url: str, base_domain: str) -> bool:
    """Return True if url belongs to the same domain as base_domain."""
    host = urlparse(url).netloc.lower().lstrip("www.")
    base = base_domain.lower().lstrip("www.")
    return host == base or host.endswith("." + base)


def path_is_relevant(path: str) -> bool:
    """
    Return True if this path is worth crawling (contains relevant words
    and does not contain noise fragments).
    """
    path_lower = path.lower()

    # skip noise paths
    for skip in SKIP_PATH_FRAGMENTS:
        if skip in path_lower:
            return False

    # allow if any relevant word is in the path
    for word in RELEVANT_LINK_WORDS:
        if word in path_lower:
            return True

    return False


# ===========================================================================
# HTTP FETCH
# ===========================================================================

def fetch_page(url: str) -> str | None:
    """
    Fetch HTML for a URL. Returns raw HTML string or None on failure.
    Includes retry logic with incremental backoff for transient failures.
    verify=False is intentional for dev/testing — remove for production.
    """
    import time
    max_retries = 3
    retry_count = 0
    backoff_delay = 0.5  # Start with 0.5 second delay

    while retry_count < max_retries:
        try:
            response = requests.get(
                url,
                headers=REQUEST_HEADERS,
                timeout=REQUEST_TIMEOUT,
                verify=False,       # dev-only: skip SSL verification
                allow_redirects=True,
            )
            if response.status_code == 200:
                return response.text
            # treat 404s / 40x silently — page just doesn't exist (don't retry)
            if response.status_code >= 400:
                return None
            # 5xx errors: retry with backoff
            if response.status_code >= 500:
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(backoff_delay * retry_count)
                continue
            return None
        except requests.Timeout:
            # Timeout: retry with backoff
            retry_count += 1
            if retry_count < max_retries:
                time.sleep(backoff_delay * retry_count)
            continue
        except requests.RequestException:
            # Other errors: retry with backoff
            retry_count += 1
            if retry_count < max_retries:
                time.sleep(backoff_delay * retry_count)
            continue

    # All retries exhausted
    return None


# ===========================================================================
# TEXT EXTRACTION
# ===========================================================================

def extract_visible_text(html: str) -> str:
    """
    Parse HTML and return only visible text (strips scripts, styles, etc.).
    Lowercased for consistent keyword matching.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "meta", "head"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    # collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text.lower()


def extract_title(html: str) -> str:
    """Extract <title> tag text from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    return title_tag.get_text(strip=True) if title_tag else ""


def extract_h1(html: str) -> str:
    """Extract first <h1> tag text from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    return h1.get_text(strip=True) if h1 else ""


def extract_internal_links(html: str, base_url: str, base_domain: str) -> list[str]:
    """
    Find all internal <a href> links in the HTML.
    Also captures link text (anchor text) for relevance scoring.
    Returns a de-duplicated list of normalized absolute URLs, sorted by relevance.
    """
    soup = BeautifulSoup(html, "html.parser")
    seen = set()
    links_with_text = []

    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        normalized = normalize_url(href, base=base_url)
        parsed = urlparse(normalized)
        if parsed.scheme not in ("http", "https"):
            continue
        if not same_domain(normalized, base_domain):
            continue
        if normalized in seen:
            continue

        seen.add(normalized)

        # Capture link text for relevance scoring
        link_text = (tag.get_text() or "").strip().lower()
        path = urlparse(normalized).path.lower()

        # Score relevance: check both path AND link text
        path_relevance = any(word in path for word in RELEVANT_LINK_WORDS)
        text_relevance = any(word in link_text for word in RELEVANT_LINK_WORDS)
        relevance_score = int(path_relevance) + int(text_relevance)  # 0, 1, or 2

        links_with_text.append((relevance_score, normalized, link_text, path))

    # Sort by relevance (high to low), maintaining stable order
    links_with_text.sort(key=lambda x: -x[0])

    return [url for _, url, _, _ in links_with_text]


# ===========================================================================
# BUSINESS NAME DETECTION
# ===========================================================================

def detect_business_name(html: str, domain: str) -> str:
    """
    Heuristic business name detection:
    1. Title tag (strip common suffixes like '| Home', '– Services')
    2. First H1
    3. Fallback: prettify domain name
    """
    title = extract_title(html)
    if title:
        # remove common page-suffix patterns
        cleaned = re.split(r"[|\-–—]", title)[0].strip()
        if cleaned:
            return cleaned

    h1 = extract_h1(html)
    if h1:
        return h1.strip()

    # fallback: strip TLD and capitalize
    name = domain.lstrip("www.").split(".")[0]
    return name.replace("-", " ").replace("_", " ").title()


# ===========================================================================
# PAGE COLLECTION / CONTROLLED CRAWL
# ===========================================================================

def collect_candidate_pages(homepage_url: str, homepage_html: str, base_domain: str) -> list[str]:
    """
    Build a focused list of pages to audit:
      1. Homepage itself
      2. Known seed paths (if they return 200)
      3. Relevant internal links found on the homepage (capped to avoid excessive crawling)

    Returns a de-duplicated list of normalized URLs, limited to ~15 pages max for performance.
    Location pages are excluded (redundant for single clinic audits - same booking/services/insurance).
    """
    candidates = set()
    candidates.add(normalize_url(homepage_url))

    # 1) Seed paths (always include these if they exist)
    parsed_home = urlparse(homepage_url)
    for path in SEED_PATHS:
        seed_url = normalize_url(
            urlunparse((parsed_home.scheme, parsed_home.netloc, path, "", "", ""))
        )
        candidates.add(seed_url)

    # 2) Relevant links from homepage
    # Let link relevance scoring guide us - don't hardcode specific path patterns
    # Every clinic has different URL structures, so we trust the dynamic discovery
    internal_links = extract_internal_links(homepage_html, homepage_url, base_domain)

    for link in internal_links:
        path = urlparse(link).path.lower()
        if not path_is_relevant(path):
            continue

        # Skip location pages entirely (redundant for clinic audits)
        if "/locations" in path or "/location" in path:
            continue

        # Skip blog pages (noise)
        if "/blog/" in path:
            continue

        candidates.add(normalize_url(link))

        # Cap at 25 additional pages (beyond homepage + seeds) for crawl balance
        if len(candidates) >= 26:  # 1 homepage + 25 others
            break

    return sorted(candidates)


# ===========================================================================
# SIGNAL DETECTION
# ===========================================================================

def count_keywords(text: str, keyword_list: list[str]) -> int:
    """Count how many times any keyword from the list appears in text."""
    count = 0
    for kw in keyword_list:
        count += text.count(kw.lower())
    return count


def find_service_categories(text: str) -> list[str]:
    """Return list of service category names found in text."""
    found = []
    for category, keywords in SERVICE_CATEGORIES.items():
        for kw in keywords:
            if kw.lower() in text:
                found.append(category)
                break   # one match per category is enough
    return found


def find_locations(text: str, title: str = "") -> list[str]:
    """
    Return Canadian cities clearly mentioned in the page.
    Prefer signals in title or repeated in body.
    Avoid counting cities that appear only once in generic/low-value text.
    Non-location contexts (e.g. "university of [city]") are excluded from
    the occurrence count so educational/historical references don't inflate
    the location list.
    """
    # Phrases that precede a city name but do NOT indicate a service location
    NON_LOCATION_PREFIXES = ("university of ", "college of ", "institute of ")

    found = set()
    for city in CANADIAN_CITIES:
        city_lower = city.lower()
        # strong signal: in title
        if city_lower in title.lower():
            found.add(city.title())
            continue
        # moderate signal: appears 2+ times in body text
        occurrences = text.count(city_lower)
        # subtract occurrences that are clearly non-location references
        for prefix in NON_LOCATION_PREFIXES:
            occurrences -= text.count(prefix + city_lower)
        if occurrences >= 2:
            found.add(city.title())
    return sorted(found)


def detect_contact_signals(text: str, raw_html: str = "") -> dict:
    """
    Detect phone, email, and address-like patterns in text.
    raw_html is used as a fallback to find emails hidden in mailto: href
    attributes (not exposed in visible text).
    """
    phones = PHONE_PATTERN.findall(text)
    emails = EMAIL_PATTERN.findall(text)
    addresses = ADDRESS_PATTERN.findall(text)

    # Fallback: extract emails from mailto: href attributes in raw HTML
    # Many sites place the email only as href="mailto:..." with display text "Email"
    if not emails and raw_html:
        mailto_matches = re.findall(
            r'mailto:([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})',
            raw_html,
            re.IGNORECASE,
        )
        emails = mailto_matches

    return {
        "phone": bool(phones),
        "email": bool(emails),
        "address": bool(addresses),
        "phone_sample": phones[0] if phones else None,
        "email_sample": emails[0] if emails else None,
    }


# ===========================================================================
# LOCAL SEO DETECTION
# ===========================================================================

def detect_map_embed(html: str) -> bool:
    """
    Return True if this page contains a Google Map iframe, Maps API script,
    or a direct Google Maps link (e.g. 'Get Directions' anchor).
    Checks: <iframe> src, Google Maps API script src, <a href> to maps.
    """
    _MAP_PATTERNS = ("maps.google", "google.com/maps", "maps.app.goo")
    soup = BeautifulSoup(html, "html.parser")
    for iframe in soup.find_all("iframe"):
        src = (iframe.get("src") or "").lower()
        if any(p in src for p in _MAP_PATTERNS):
            return True
    for script in soup.find_all("script"):
        src = (script.get("src") or "").lower()
        if "maps.googleapis.com" in src:
            return True
    # Also catch <a href="https://google.com/maps/..."> direction links
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").lower()
        if any(p in href for p in _MAP_PATTERNS):
            return True
    return False


def detect_schema_markup(html: str) -> bool:
    """
    Return True if this page contains LocalBusiness (or related) JSON-LD schema.
    Checks <script type="application/ld+json"> blocks for @type values that
    indicate a local business entry.
    """
    LOCAL_SCHEMA_TYPES = {
        '"localbusiness"', '"medicalbusiness"', '"healthandbeautybusiness"',
        '"physician"', '"medicalclinic"', '"physiotherapist"',
    }
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        content = (script.string or "").lower()
        if '"@type"' in content and any(t in content for t in LOCAL_SCHEMA_TYPES):
            return True
    return False


# ===========================================================================
# META DESCRIPTION DETECTION
# ===========================================================================

def detect_meta_descriptions(html: str) -> dict:
    """
    Check if page has a meta description tag and validate length.
    Optimal length: 150-160 characters (Google's truncation point).

    Returns:
      has_description : bool
      length          : int (0 if missing)
      status          : 'missing' | 'too_short' | 'too_long' | 'ok'
      content_preview : str (first 100 chars or empty)
      details         : list[str] (findings)
    """
    soup = BeautifulSoup(html, "html.parser")
    meta_desc = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})

    if not meta_desc:
        return {
            "has_description": False,
            "length": 0,
            "status": "missing",
            "content_preview": "",
            "details": ["Meta description missing — Google will pull random text from page for search snippet."],
        }

    content = (meta_desc.get("content") or "").strip()
    length = len(content)

    if length == 0:
        return {
            "has_description": False,
            "length": 0,
            "status": "missing",
            "content_preview": "",
            "details": ["Meta description tag exists but is empty."],
        }

    preview = content[:100] + ("…" if len(content) > 100 else "")

    if length < 120:
        return {
            "has_description": True,
            "length": length,
            "status": "too_short",
            "content_preview": preview,
            "details": [
                f"Meta description too short ({length} chars). Recommended: 150-160 characters.",
                f"Preview: '{preview}'"
            ],
        }
    elif length > 160:
        return {
            "has_description": True,
            "length": length,
            "status": "too_long",
            "content_preview": preview,
            "details": [
                f"Meta description too long ({length} chars). Google will truncate in search results.",
                f"Target: 150-160 characters."
            ],
        }

    return {
        "has_description": True,
        "length": length,
        "status": "ok",
        "content_preview": preview,
        "details": ["Meta description present and properly sized."],
    }


# ===========================================================================
# CONTACT QUALITY DETECTION
# ===========================================================================

def detect_contact_quality(html: str, text: str) -> dict:
    """
    Detect quality signals beyond basic phone/email/address presence.

    Parameters:
      html : raw HTML string
      text : lowercased visible text (from extract_visible_text)

    Returns:
      clickable_phone         : bool — <a href="tel:..."> present
      has_hours               : bool — hours of operation displayed
      contact_in_header_footer: bool — phone or email found in <header>/<footer>/<nav>
    """
    soup = BeautifulSoup(html, "html.parser")

    # --- Clickable phone: tel: href ---
    clickable_phone = bool(
        soup.find("a", href=re.compile(r"^tel:", re.IGNORECASE))
    )

    # --- Hours of operation ---
    has_hours = any(kw in text for kw in HOURS_KEYWORDS)
    if not has_hours:
        # Fallback: day name + time pattern appearing together on page
        has_day = any(day in text for day in _DAYS_OF_WEEK)
        has_time = bool(_TIME_PATTERN.search(text))
        has_hours = has_day and has_time

    # --- Contact info in structural elements (header / footer / nav) ---
    contact_in_header_footer = False
    for tag_name in ("header", "footer", "nav"):
        for elem in soup.find_all(tag_name):
            elem_text = elem.get_text(separator=" ")
            if PHONE_PATTERN.search(elem_text) or EMAIL_PATTERN.search(elem_text):
                contact_in_header_footer = True
                break
        if contact_in_header_footer:
            break

    return {
        "clickable_phone":          clickable_phone,
        "has_hours":                has_hours,
        "contact_in_header_footer": contact_in_header_footer,
    }


# ===========================================================================
# REVIEW SCHEMA EXTRACTION
# ===========================================================================

def extract_review_schema(html: str) -> dict:
    """
    Extract review metrics from JSON-LD schema.
    Returns:
      rating_value: float | None (e.g., 4.7)
      review_count: int | None (e.g., 42)
      most_recent_date: str | None (e.g., "2024-11-15")
    """
    soup = BeautifulSoup(html, "html.parser")
    rating_value = None
    review_count = None
    most_recent_date = None

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "{}")

            # Look for aggregateRating in LocalBusiness, Organization, or AggregateRating schema
            agg_rating = data.get("aggregateRating") or {}
            if isinstance(agg_rating, dict):
                if agg_rating.get("ratingValue"):
                    rating_value = float(agg_rating.get("ratingValue"))
                if agg_rating.get("reviewCount"):
                    review_count = int(agg_rating.get("reviewCount"))

            # Look for individual reviews with dates
            reviews = data.get("review", [])
            if isinstance(reviews, list):
                for review in reviews:
                    if isinstance(review, dict) and review.get("datePublished"):
                        date_str = review.get("datePublished")
                        if most_recent_date is None or date_str > most_recent_date:
                            most_recent_date = date_str
        except (json.JSONDecodeError, ValueError, TypeError):
            continue

    return {
        "rating_value": rating_value,
        "review_count": review_count,
        "most_recent_date": most_recent_date,
    }


# ===========================================================================
# TEAM CREDIBILITY DETECTION
# ===========================================================================

def detect_team_credibility(html: str, text: str) -> dict:
    """
    Detect team credentials, depth, and bio quality.

    Returns:
      has_team_page: bool — team page detected
      team_member_count: int — approximate number of team members with credentials
      has_detailed_bios: bool — team members have substantial bios (>100 chars per member)
      credentialed_members: int — count of members with recognizable credentials
      details: list[str] — findings about team
    """
    soup = BeautifulSoup(html, "html.parser")
    details = []

    has_team_page = False
    team_member_count = 0
    credentialed_members = 0
    has_detailed_bios = False

    # Look for team member containers (common patterns)
    # Could be: .team-member, [data-member], .staff-card, etc.
    team_containers = soup.find_all(["div", "article"], class_=lambda x: x and any(
        word in x.lower() for word in ["team", "staff", "member", "provider", "doctor", "therapist"]
    ))

    if team_containers:
        has_team_page = True
        team_member_count = len(team_containers)

        # Check if members have credentials and bios
        total_bio_length = 0
        for container in team_containers:
            container_text = container.get_text(strip=True)
            total_bio_length += len(container_text)

            # Check for credential keywords in container
            if any(term.lower() in container_text.lower() for term in CREDENTIAL_TERMS):
                credentialed_members += 1

        # Average bio length per member
        avg_bio_length = total_bio_length / len(team_containers) if team_containers else 0
        has_detailed_bios = avg_bio_length > 100  # More than 100 chars per member = detailed

        if credentialed_members > 0:
            details.append(f"{credentialed_members}/{team_member_count} team members have recognizable credentials.")
        else:
            details.append(f"Team page shows {team_member_count} members but credentials not clearly listed.")

        if has_detailed_bios:
            details.append(f"Team members have detailed bios (avg {int(avg_bio_length)} characters) — builds credibility.")

    return {
        "has_team_page": has_team_page,
        "team_member_count": team_member_count,
        "credentialed_members": credentialed_members,
        "has_detailed_bios": has_detailed_bios,
        "details": details,
    }


# ===========================================================================
# TRUST SIGNAL DETECTION
# ===========================================================================

def detect_trust_signals(html: str, text: str) -> dict:
    """
    Detect trust-building and review signals on a single page.

    Parameters:
      html : raw HTML string
      text : lowercased visible text (from extract_visible_text)

    Returns:
      has_review_widget      : bool — third-party review widget embedded
      has_testimonial_content: bool — actual quote/testimonial text present
      testimonial_count      : int  — approximate number of distinct testimonials
      has_star_rating        : bool — star rating displayed
      review_platforms_linked: list[str] — platform names linked (e.g. 'Google Business')
      has_credentials        : bool — professional credential terms found
      has_professional_assoc : bool — professional association mention found
      has_years_in_practice  : bool — establishment date or experience language
      details                : list[str]
    """
    soup = BeautifulSoup(html, "html.parser")
    details = []

    # --- 1. Review widget: third-party embed domains in any src/href ---
    has_review_widget = False
    for tag in soup.find_all(True):
        for attr in ("src", "href", "data-src"):
            val = (tag.get(attr) or "").lower()
            if any(sig in val for sig in REVIEW_WIDGET_SIGNATURES):
                has_review_widget = True
                details.append(f"Review widget detected (source: {val[:60]}).")
                break
        if has_review_widget:
            break

    # --- 2. Testimonial content: blockquotes, review schema, testimonial sections ---
    testimonial_count = 0
    has_testimonial_content = False

    # blockquotes with real content
    for bq in soup.find_all("blockquote"):
        if len(bq.get_text(strip=True)) > 30:
            testimonial_count += 1

    # elements with testimonial/review/quote in class or id
    # Only count leaf-level items (elements that do NOT contain another matching element).
    # This prevents containers like .sow-testimonials from being counted alongside
    # their children .sow-testimonial, which would inflate the count for each testimonial.
    if testimonial_count == 0:
        _TESTIM_KWS = ("testimonial", "review-item", "quote", "client-review")
        matching_elems = []
        for elem in soup.find_all(True):
            cls = " ".join(elem.get("class") or []).lower()
            eid = (elem.get("id") or "").lower()
            if any(kw in cls or kw in eid for kw in _TESTIM_KWS):
                if len(elem.get_text(strip=True)) > 80:
                    matching_elems.append(elem)
        for elem in matching_elems:
            # Skip if this element contains any other matching element (it's a container)
            has_child_match = any(
                elem is not child and child in matching_elems
                for child in elem.find_all(True)
            )
            if not has_child_match:
                testimonial_count += 1

    # Review JSON-LD schema
    for script in soup.find_all("script", type="application/ld+json"):
        content = (script.string or "").lower()
        if '"@type"' in content and ('"review"' in content or '"aggregaterating"' in content):
            testimonial_count = max(testimonial_count, 1)
            break

    has_testimonial_content = testimonial_count > 0
    if has_testimonial_content:
        details.append(f"Testimonial/review content detected ({testimonial_count} item(s)).")

    # --- 3. Star ratings ---
    has_star_rating = False
    star_chars = ["★", "☆", "⭐", "🌟"]
    if any(ch in html for ch in star_chars):
        has_star_rating = True
    if not has_star_rating and re.search(r"\b[4-5][\.,]\d\s*(out of 5|\/5|stars?)", text):
        has_star_rating = True
    if not has_star_rating:
        for script in soup.find_all("script", type="application/ld+json"):
            content = (script.string or "").lower()
            if '"ratingvalue"' in content or '"aggregaterating"' in content:
                has_star_rating = True
                break
    if has_star_rating:
        details.append("Star rating displayed.")

    # --- 4. Review platform links ---
    review_platforms_linked = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].lower()
        for platform_name, domains in REVIEW_PLATFORM_DOMAINS.items():
            if any(d in href for d in domains) and platform_name not in review_platforms_linked:
                review_platforms_linked.append(platform_name)
    if review_platforms_linked:
        details.append(f"Review platform link(s) found: {', '.join(review_platforms_linked)}.")

    # --- 5. Credential terms ---
    has_credentials = any(term in text for term in CREDENTIAL_TERMS)
    if has_credentials:
        details.append("Professional credential terms detected (e.g. 'Registered Physiotherapist').")

    # --- 6. Professional association ---
    has_professional_assoc = any(term in text for term in PROFESSIONAL_ASSOC_TERMS)
    if has_professional_assoc:
        details.append("Professional association mentioned.")

    # --- 7. Years in practice / establishment ---
    has_years_in_practice = any(phrase in text for phrase in YEARS_IN_PRACTICE_PHRASES)
    if has_years_in_practice:
        details.append("Establishment date or years-in-practice language detected.")

    # --- 8. Schema-based review metrics (Google rating + count + recency) ---
    schema_data = extract_review_schema(html)
    rating_value = schema_data.get("rating_value")
    review_count = schema_data.get("review_count")
    most_recent_date = schema_data.get("most_recent_date")

    # --- 9. Detect false/misleading review claims ---
    # Check if visible text claims a rating that differs from schema
    claimed_rating = None
    has_misleading_claim = False

    # Look for patterns like "5 star", "5-star", "4.9 rating" in visible text
    rating_patterns = [
        r'\b(5|4\.9|4\.8)\s*(?:star|rating)(?:\s|$)',  # "5 star rating"
        r'(?:^|\s)(5|4\.9|4\.8)(?:\s+out\s+of\s+5|/5)',  # "5 out of 5" or "5/5"
        r'(?:rated|rating).*?\b(5|4\.9|4\.8)\b',  # "rated 5"
    ]
    for pattern in rating_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            claimed_rating = float(match.group(1))
            break

    # Compare claimed rating to actual schema rating
    if claimed_rating is not None:
        if rating_value is None:
            # Site claims a rating but has NO schema markup — suspicious, likely outdated
            has_misleading_claim = True
            details.insert(0, f"⚠️ UNVERIFIED: Site claims {claimed_rating}★ rating but no Google schema data found — claim may be outdated or unverified.")
        elif abs(claimed_rating - rating_value) >= 0.5:
            # Claimed and actual differ significantly
            has_misleading_claim = True
            details.insert(0, f"⚠️ MISLEADING: Site claims {claimed_rating}★ but Google schema shows {rating_value}★ ({review_count} reviews).")
        else:
            # Claims match or are close
            details.append(f"Google review schema found: {rating_value}★ ({review_count} reviews).")
    elif rating_value is not None and review_count is not None:
        details.append(f"Google review schema found: {rating_value}★ ({review_count} reviews).")

    if most_recent_date:
        details.append(f"Most recent review date in schema: {most_recent_date}.")

    return {
        "has_review_widget":       has_review_widget,
        "has_testimonial_content": has_testimonial_content,
        "testimonial_count":       testimonial_count,
        "has_star_rating":         has_star_rating,
        "review_platforms_linked": review_platforms_linked,
        "has_credentials":         has_credentials,
        "has_professional_assoc":  has_professional_assoc,
        "has_years_in_practice":   has_years_in_practice,
        "rating_value":            rating_value,
        "review_count":            review_count,
        "most_recent_date":        most_recent_date,
        "has_misleading_claim":    has_misleading_claim,
        "claimed_rating":          claimed_rating,
        "details":                 details,
    }


# ===========================================================================
# BOOKING SYSTEM DETECTION
# ===========================================================================

def detect_booking_system(html: str, url: str) -> dict:
    """
    Detect what booking system (if any) is used on this page.

    Returns a dict with:
      type         : 'platform' | 'internal_booking' | 'form' | 'phone_only' | 'none'
      platform_name: str | None   (e.g. 'Janeapp')
      platform_links: list[str]   (sample hrefs/srcs where platform was found)
      has_contact_form: bool
      call_to_book_language: bool
      details      : list[str]    (human-readable findings)

    Detection order (highest confidence first):
      1. Known booking platform found in href/src/action/script → 'platform'
      2. "Book Online" or similar button/link found → 'internal_booking'
      3. <form> tag present on a contact/booking page OR with booking-like fields → 'form'
      4. Phone-only booking language in visible text → 'phone_only'
      5. None of the above → 'none'
    """
    soup = BeautifulSoup(html, "html.parser")
    text_lower = extract_visible_text(html)   # already lowercased

    platform_found = None
    platform_links = []

    # --- 1. Scan link/embed attributes for known booking platform domains ---
    for tag in soup.find_all(True):
        for attr in ("href", "src", "action", "data-src", "data-url"):
            val = tag.get(attr, "") or ""
            val_lower = val.lower()
            for p_name, domains in BOOKING_PLATFORM_SIGNATURES.items():
                for domain in domains:
                    if domain in val_lower:
                        platform_found = p_name
                        platform_links.append(val)
                        break
                if platform_found:
                    break
        if platform_found:
            break

    # --- 2. Scan inline <script> content for platform domains ---
    if not platform_found:
        for script in soup.find_all("script"):
            script_text = (script.string or "").lower()
            for p_name, domains in BOOKING_PLATFORM_SIGNATURES.items():
                for domain in domains:
                    if domain in script_text:
                        platform_found = p_name
                        platform_links.append(f"[inline script: {domain}]")
                        break
                if platform_found:
                    break
            if platform_found:
                break

    if platform_found:
        sample = ", ".join(platform_links[:2])
        return {
            "type": "platform",
            "platform_name": platform_found,
            "platform_links": platform_links[:3],
            "has_contact_form": False,
            "call_to_book_language": False,
            "details": [
                f"{platform_found} booking platform detected (found in: {sample})"
            ],
        }

    # --- 2b. Check for "Book Online" buttons/links ---
    # NOTE: Just finding a "Book Online" link is NOT enough to claim online booking capability.
    # It could link to a contact form. We only mark it as internal_booking if we also
    # confirm no contact form exists. For now, we skip this detection to avoid false positives.
    # Real booking systems are detected via platform signatures (above) or contact form detection (below).

    # --- 3. Check for contact/booking forms ---
    has_contact_form = False
    page_path = urlparse(url).path.lower()
    is_contact_or_booking_page = any(
        kw in page_path for kw in ("contact", "book", "appointment", "request")
    )

    for form in soup.find_all("form"):
        action = (form.get("action") or "").lower()
        # Collect names/placeholders from all form fields
        fields = form.find_all(["input", "textarea", "select"])
        field_text = " ".join(
            (f.get("name") or f.get("placeholder") or f.get("type") or "").lower()
            for f in fields
        )
        # Count as a contact form if on a contact/booking page OR has typical contact fields
        if is_contact_or_booking_page or any(
            kw in field_text
            for kw in ("name", "email", "message", "phone", "date", "appointment", "subject")
        ):
            has_contact_form = True
            break

    # --- 4. Phone-only booking language ---
    call_to_book = any(phrase in text_lower for phrase in CALL_TO_BOOK_PHRASES)

    if has_contact_form:
        return {
            "type": "form",
            "platform_name": None,
            "platform_links": [],
            "has_contact_form": True,
            "call_to_book_language": call_to_book,
            "details": [
                "Contact form detected — patients submit a form and wait for callback. "
                "No real-time online booking system found."
            ],
        }

    if call_to_book:
        return {
            "type": "phone_only",
            "platform_name": None,
            "platform_links": [],
            "has_contact_form": False,
            "call_to_book_language": True,
            "details": [
                "Phone-only booking detected — site directs patients to call. "
                "No online booking or contact form found."
            ],
        }

    return {
        "type": "none",
        "platform_name": None,
        "platform_links": [],
        "has_contact_form": False,
        "call_to_book_language": False,
        "details": ["No booking system detected on this page."],
    }


# ===========================================================================
# INSURANCE DEPTH DETECTION
# ===========================================================================

def assess_insurance_depth(text: str, url: str) -> dict:
    """
    Assess the quality of insurance/billing information on a page.

    Returns a dict with:
      specificity    : 'none' | 'vague' | 'moderate' | 'strong'
      providers_found: list[str]  — named providers detected (e.g. ['Sun Life', 'Manulife'])
      direct_billing : bool       — 'direct billing' explicitly mentioned
      details        : list[str]  — human-readable findings

    Specificity tiers:
      none     — no insurance keywords at all
      vague    — insurance mentioned but no named providers and no direct billing
      moderate — named providers OR direct billing, but not both
      strong   — named providers AND direct billing explicitly mentioned
    """
    # text is already lowercased from extract_visible_text()

    # Check whether any insurance keyword appears at all
    has_any_insurance = any(kw in text for kw in INSURANCE_KEYWORDS)
    if not has_any_insurance:
        return {
            "specificity": "none",
            "providers_found": [],
            "direct_billing": False,
            "details": ["No insurance or billing information found on this page."],
        }

    # Negation words — used by both provider and direct-billing checks below.
    # A 60-80 char window before each match is scanned for these to avoid
    # false positives like "we do not see WSIB clients" or "unable to bill directly".
    _NEGATIONS = ("unable", "cannot", "can't", "not able", "don't", "do not",
                  "no longer", "not see", "does not see", "do not see",
                  "not accept", "does not accept", "no longer accept")

    # Check for named providers — a provider counts only when at least one
    # mention has no negation in the 80-char window before OR the 120-char
    # window after the match. The after-window catches FAQ Q&A patterns like
    # "do you see WSIB clients? No, we do not." where the negation follows.
    providers_found = []
    for provider_name, aliases in INSURANCE_PROVIDERS.items():
        provider_confirmed = False
        for alias in aliases:
            search_start = 0
            while True:
                idx = text.find(alias, search_start)
                if idx == -1:
                    break
                end = idx + len(alias)
                window_before = text[max(0, idx - 80):idx]
                window_after  = text[end:end + 120]
                negated = (
                    any(neg in window_before for neg in _NEGATIONS)
                    or any(neg in window_after for neg in _NEGATIONS)
                )
                if not negated:
                    provider_confirmed = True
                    break
                search_start = idx + 1
            if provider_confirmed:
                break
        if provider_confirmed:
            providers_found.append(provider_name)

    # Check for explicit direct billing language — skip if negated.
    direct_billing = False
    for phrase in DIRECT_BILLING_PHRASES:
        idx = text.find(phrase)
        if idx == -1:
            continue
        window = text[max(0, idx - 60):idx]
        if not any(neg in window for neg in _NEGATIONS):
            direct_billing = True
            break

    # Determine specificity
    if providers_found and direct_billing:
        specificity = "strong"
        details = [
            f"Direct billing explicitly mentioned. Named providers found: {', '.join(providers_found)}."
        ]
    elif providers_found:
        specificity = "moderate"
        details = [
            f"Providers named ({', '.join(providers_found)}) but direct billing not explicitly stated."
        ]
    elif direct_billing:
        specificity = "moderate"
        details = [
            "Direct billing mentioned but no specific insurance providers listed."
        ]
    else:
        specificity = "vague"
        details = [
            "Insurance mentioned but vague — no providers named, no direct billing explained. "
            "Patients cannot determine if their plan is accepted."
        ]

    return {
        "specificity": specificity,
        "providers_found": providers_found,
        "direct_billing": direct_billing,
        "details": details,
    }


# ===========================================================================
# MOBILE READINESS — PER-PAGE DETECTION
# ===========================================================================

def detect_mobile_signals(html: str, url: str) -> dict:
    """
    Detect mobile-readiness signals on a single page.
    All fields are raw booleans/counts — scoring happens in assess_mobile_readiness().
    """
    soup = BeautifulSoup(html, "html.parser")
    html_lower = html.lower()

    # 1. Viewport meta tag
    has_viewport_tag = bool(
        soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})
    )

    # 2. Media queries in inline <style> blocks
    has_media_queries = False
    for style_tag in soup.find_all("style"):
        if style_tag.string and "@media" in style_tag.string.lower():
            has_media_queries = True
            break

    # 3. Mobile navigation patterns (hamburger menus, toggle menus)
    _MOBILE_NAV_PATTERNS = [
        "mobile-menu", "mobile-nav", "nav-toggle", "burger", "hamburger",
        "navbar-toggler", "menu-toggle", "offcanvas", "sidenav",
        "nav-open", "menu-open",
    ]
    has_mobile_nav = any(p in html_lower for p in _MOBILE_NAV_PATTERNS)
    # Also check data-toggle attribute (Bootstrap etc.)
    if not has_mobile_nav and soup.find(attrs={"data-toggle": True}):
        has_mobile_nav = True

    # 4. Small font-size in inline styles or <style> blocks (< 14px)
    _px_font_re = re.compile(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", re.IGNORECASE)
    small_font_detected = False
    for tag in soup.find_all(style=True):
        for m in _px_font_re.finditer(tag.get("style", "")):
            if float(m.group(1)) < 14:
                small_font_detected = True
                break
    if not small_font_detected:
        for style_tag in soup.find_all("style"):
            if style_tag.string:
                for m in _px_font_re.finditer(style_tag.string):
                    if float(m.group(1)) < 14:
                        small_font_detected = True
                        break

    # 5. Tap targets — links/buttons with explicit inline width or height < 44px
    _dim_re = re.compile(r"(?:width|height)\s*:\s*(\d+)px", re.IGNORECASE)
    small_tap_target = False
    for tag in soup.find_all(["a", "button"], style=True):
        for m in _dim_re.finditer(tag.get("style", "")):
            if int(m.group(1)) < 44:
                small_tap_target = True
                break

    # 6. Horizontal overflow risk — inline width > 400px
    _width_re = re.compile(r"(?:^|;)\s*(?:min-)?width\s*:\s*(\d+)px", re.IGNORECASE)
    fixed_wide_count = 0
    for tag in soup.find_all(style=True):
        for m in _width_re.finditer(tag.get("style", "")):
            if int(m.group(1)) > 400:
                fixed_wide_count += 1
                break  # count once per element

    # 7. Image count and alt text audit
    all_imgs = soup.find_all("img")
    img_count = len(all_imgs)
    imgs_missing_dims = sum(
        1 for img in all_imgs
        if not (img.get("width") and img.get("height"))
    )
    imgs_missing_alt = sum(
        1 for img in all_imgs
        if not img.get("alt")
    )
    alt_coverage_pct = (
        round(((img_count - imgs_missing_alt) / img_count * 100), 1)
        if img_count > 0 else 100
    )

    # 8. Render-blocking scripts (external scripts without async or defer)
    render_blocking_scripts = sum(
        1 for s in soup.find_all("script", src=True)
        if not s.get("async") and not s.get("defer") and s.get("defer") != ""
    )

    # 9. HTML page size
    html_size_bytes = len(html.encode("utf-8"))

    return {
        "url": url,
        "has_viewport_tag": has_viewport_tag,
        "has_media_queries": has_media_queries,
        "has_mobile_nav": has_mobile_nav,
        "small_font_detected": small_font_detected,
        "small_tap_target": small_tap_target,
        "fixed_wide_count": fixed_wide_count,
        "img_count": img_count,
        "imgs_missing_dims": imgs_missing_dims,
        "imgs_missing_alt": imgs_missing_alt,
        "alt_coverage_pct": alt_coverage_pct,
        "render_blocking_scripts": render_blocking_scripts,
        "html_size_bytes": html_size_bytes,
    }


# ===========================================================================
# GOOGLE PAGESPEED INSIGHTS INTEGRATION
# ===========================================================================

def check_google_pagespeed(url: str, api_key: str = None) -> dict:
    """
    Call Google PageSpeed Insights API to get real mobile performance metrics.
    Requires API key from Google Cloud Console (free tier).
    If api_key is None or API fails, returns graceful "skipped" response.

    Returns:
      mobile_score      : int (0-100, or None if skipped)
      lcp               : str (e.g. "3.2 s")
      cls               : str (e.g. "0.12")
      speed_index       : str (e.g. "5.1 s")
      status            : 'ok' | 'skipped' | 'error'
      error_detail      : str (if status == 'error')
      details           : list[str] (findings)
    """
    # If no API key provided, skip gracefully
    if not api_key:
        return {
            "mobile_score": None,
            "lcp": None,
            "cls": None,
            "speed_index": None,
            "status": "skipped",
            "error_detail": "PageSpeed API key not configured",
            "details": ["Google PageSpeed Insights skipped (no API key). "
                       "To enable: get free API key from Google Cloud Console & set GOOGLE_PAGESPEED_API_KEY env var."]
        }

    try:
        # Use Google PageSpeed Insights API via googleapis.com (most reliable endpoint)
        # Note: PageSpeed API runs full Lighthouse analysis, which can be slow
        endpoint = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
        params = {
            "url": url,
            "key": api_key,
            "strategy": "mobile",
            "category": "performance"
        }

        # Lighthouse analysis takes time; use generous timeout (60s)
        # If network blocks pagespeedonline.com, this endpoint typically works better
        response = requests.get(endpoint, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()

        # Extract lighthouse results
        lh_result = data.get("lighthouseResult", {})
        categories = lh_result.get("categories", {})
        audits = lh_result.get("audits", {})

        # Performance score (0-100)
        perf_score = categories.get("performance", {}).get("score")
        mobile_score = round(perf_score * 100) if perf_score is not None else None

        # Extract metric values
        def get_metric(audit_key):
            return audits.get(audit_key, {}).get("displayValue", None)

        lcp = get_metric("largest-contentful-paint")
        cls = get_metric("cumulative-layout-shift")
        speed_index = get_metric("speed-index")

        # Interpret score
        if mobile_score is None:
            status = "error"
            detail = "Could not parse performance score from API response"
        elif mobile_score >= 90:
            status = "ok"
            detail = f"Excellent mobile performance ({mobile_score}/100) — fast load time."
        elif mobile_score >= 75:
            status = "ok"
            detail = f"Good mobile performance ({mobile_score}/100) — acceptable speed."
        elif mobile_score >= 50:
            status = "warning"
            detail = f"Moderate mobile performance ({mobile_score}/100) — room for improvement."
        else:
            status = "warning"
            detail = f"Poor mobile performance ({mobile_score}/100) — patients on phones wait too long."

        details = [detail]
        if lcp:
            details.append(f"Largest Contentful Paint: {lcp} (target: <2.5s)")
        if cls:
            details.append(f"Cumulative Layout Shift: {cls} (target: <0.1)")
        if speed_index:
            details.append(f"Speed Index: {speed_index} (target: <3.4s)")

        return {
            "mobile_score": mobile_score,
            "lcp": lcp,
            "cls": cls,
            "speed_index": speed_index,
            "status": status,
            "error_detail": None,
            "details": details,
        }

    except requests.RequestException as e:
        return {
            "mobile_score": None,
            "lcp": None,
            "cls": None,
            "speed_index": None,
            "status": "error",
            "error_detail": f"PageSpeed API error: {str(e)[:80]}",
            "details": [f"Could not reach Google PageSpeed API: {str(e)[:120]}"],
        }
    except (KeyError, ValueError, TypeError) as e:
        return {
            "mobile_score": None,
            "lcp": None,
            "cls": None,
            "speed_index": None,
            "status": "error",
            "error_detail": f"PageSpeed API response parsing failed: {str(e)[:80]}",
            "details": ["Google PageSpeed API returned unexpected response format."],
        }


# ===========================================================================
# PER-PAGE SIGNAL EXTRACTION
# ===========================================================================

def extract_page_signals(url: str, html: str, pagespeed_api_key: str = None) -> dict:
    """
    Extract all signals for a single page.
    Returns a dict suitable for the JSON output and report rendering.
    pagespeed_api_key: Optional Google PageSpeed Insights API key for real mobile performance testing.
    """
    text = extract_visible_text(html)
    title = extract_title(html)

    booking_count = count_keywords(text, BOOKING_KEYWORDS)
    review_count = count_keywords(text, REVIEW_KEYWORDS)
    services = find_service_categories(text)
    contact = detect_contact_signals(text, raw_html=html)
    insurance_count = count_keywords(text, INSURANCE_KEYWORDS)
    insurance_depth = assess_insurance_depth(text, url)
    locations = find_locations(text, title=title)
    neighbourhood_detected = any(term in text for term in NEIGHBOURHOOD_TERMS)
    contact_quality = detect_contact_quality(html, text)
    trust_signals = detect_trust_signals(html, text)
    team_credibility = detect_team_credibility(html, text)
    booking_system = detect_booking_system(html, url)
    map_embed = detect_map_embed(html)
    local_schema = detect_schema_markup(html)
    mobile_signals = detect_mobile_signals(html, url)
    meta_descriptions = detect_meta_descriptions(html)
    pagespeed = check_google_pagespeed(url, api_key=pagespeed_api_key)

    return {
        "url": url,
        "title": title,
        "visible_text_length": len(text),
        "booking_keyword_count": booking_count,
        "booking_system": booking_system,
        "review_keyword_count": review_count,
        "service_categories": services,
        "contact": contact,
        "insurance_mentioned": insurance_count > 0,
        "insurance_count": insurance_count,
        "insurance_depth": insurance_depth,
        "locations": locations,
        "neighbourhood_detected": neighbourhood_detected,
        "contact_quality": contact_quality,
        "trust_signals": trust_signals,
        "team_credibility": team_credibility,
        "map_embed": map_embed,
        "local_schema": local_schema,
        "mobile_signals": mobile_signals,
        "meta_descriptions": meta_descriptions,
        "pagespeed": pagespeed,
    }


# ===========================================================================
# SERVICE PRESENTATION ASSESSMENT
# ===========================================================================

def assess_service_presentation(page_signals: list[dict], homepage_url: str) -> dict:
    """
    Assess the quality of how services are presented across all crawled pages.
    Called once after all pages are analyzed — not a per-page function.

    Returns:
      has_services_page          : bool — a /services page was crawled
      services_page_url          : str | None
      has_homepage_services      : bool — services detected on the homepage
      homepage_service_count     : int
      service_count              : int  — union of homepage + services page categories
      services_have_descriptions : bool — services page text suggests more than a name list
      services_page_text_length  : int  — raw visible text length of services page
      has_dedicated_subpages     : bool — e.g. /services/physiotherapy exists
      subpages_found             : list[str]
      details                    : list[str]

    Heuristic for "has descriptions":
      The services page visible text length > 1200 chars.
      A page that only lists service names with nav/footer will typically be
      under 800 chars. A page with per-service paragraphs will be 1500+.
    """
    homepage_norm = normalize_url(homepage_url)

    has_services_page = False
    services_page_url = None
    services_page_text_length = 0
    services_page_service_count = 0
    has_homepage_services = False
    homepage_service_count = 0
    all_scoring_services = set()
    subpages_found = []

    for ps in page_signals:
        url_norm = normalize_url(ps["url"])
        path = urlparse(url_norm).path.lower().rstrip("/") or "/"
        is_homepage = (url_norm == homepage_norm)

        # Dedicated sub-pages: path matches /services/<something>, /treatments/<something>, /conditions/<something>, etc.
        if re.match(r"^/(services?|treatments?|conditions?)/.+", path):
            subpages_found.append(ps["url"])

        # Identify the root services page vs. sub-pages
        is_services_root = path in ("/services", "/service", "/treatments", "/treatment", "/conditions", "/condition", "/our-treatments", "/our-conditions")
        is_services_page = any(kw in path for kw in ("service", "treatment", "condition")) and not is_homepage

        if is_homepage:
            homepage_service_count = len(ps["service_categories"])
            has_homepage_services = homepage_service_count > 0
            for svc in ps["service_categories"]:
                all_scoring_services.add(svc)

        if is_services_page:
            for svc in ps["service_categories"]:
                all_scoring_services.add(svc)
            # Prefer the root /services page for the description heuristic;
            # fall back to any services page if no root found yet
            if is_services_root or not has_services_page:
                has_services_page = True
                services_page_url = ps["url"]
                services_page_text_length = ps.get("visible_text_length", 0)
                services_page_service_count = len(ps["service_categories"])

    service_count = len(all_scoring_services)

    # "Has descriptions" heuristic:
    # A page listing only service names (with nav/footer) will be under ~800 chars.
    # A page with per-service descriptions will be 1500+ chars.
    services_have_descriptions = (
        has_services_page and services_page_text_length > 1200
    )

    # Build details
    details = []
    if has_services_page:
        desc_label = "appears to have descriptions" if services_have_descriptions else "appears to be a list of names only"
        details.append(
            f"Services page found ({services_page_url}) — {desc_label} "
            f"(visible text: {services_page_text_length} chars)."
        )
    else:
        details.append("No dedicated services page found.")

    if has_homepage_services:
        details.append(f"{homepage_service_count} service category(ies) visible on homepage.")
    else:
        details.append("No service categories detected on homepage.")

    if subpages_found:
        details.append(
            f"{len(subpages_found)} dedicated service sub-page(s) found: "
            f"{', '.join(subpages_found[:3])}{'...' if len(subpages_found) > 3 else ''}."
        )
    else:
        details.append("No dedicated sub-pages for individual services (e.g. /services/physiotherapy).")

    details.append(f"Total service categories (homepage + services page): {service_count}.")

    return {
        "has_services_page": has_services_page,
        "services_page_url": services_page_url,
        "has_homepage_services": has_homepage_services,
        "homepage_service_count": homepage_service_count,
        "service_count": service_count,
        "services_have_descriptions": services_have_descriptions,
        "services_page_text_length": services_page_text_length,
        "has_dedicated_subpages": bool(subpages_found),
        "subpages_found": subpages_found,
        "details": details,
    }


# ===========================================================================
# MOBILE READINESS — AGGREGATE ASSESSMENT
# ===========================================================================

def assess_mobile_readiness(
    page_signals: list[dict],
    homepage_url: str,
    booking_type: str,
    booking_platform: str,
    booking_on_homepage: bool,
) -> dict:
    """
    Aggregate mobile-readiness signals across all pages and produce findings.
    Called once after all pages are analyzed.
    booking_type/platform/on_homepage are pre-aggregated from aggregate_signals().
    """
    homepage_norm = normalize_url(homepage_url)

    homepage_has_viewport = False
    any_page_has_viewport = False
    any_page_has_media_queries = False
    any_page_has_mobile_nav = False
    total_imgs = 0
    total_imgs_missing_dims = 0
    max_render_blocking = 0
    max_html_size = 0
    heavy_pages = []
    small_font_found = False
    small_tap_found = False
    fixed_wide_pages = []

    for ps in page_signals:
        ms = ps.get("mobile_signals", {})
        is_homepage = (normalize_url(ps["url"]) == homepage_norm)

        if ms.get("has_viewport_tag"):
            any_page_has_viewport = True
            if is_homepage:
                homepage_has_viewport = True
        if ms.get("has_media_queries"):
            any_page_has_media_queries = True
        if ms.get("has_mobile_nav"):
            any_page_has_mobile_nav = True

        total_imgs += ms.get("img_count", 0)
        total_imgs_missing_dims += ms.get("imgs_missing_dims", 0)

        rbs = ms.get("render_blocking_scripts", 0)
        if rbs > max_render_blocking:
            max_render_blocking = rbs

        html_size = ms.get("html_size_bytes", 0)
        if html_size > max_html_size:
            max_html_size = html_size
        if html_size > 500_000:
            heavy_pages.append(ps["url"])

        if ms.get("small_font_detected"):
            small_font_found = True
        if ms.get("small_tap_target"):
            small_tap_found = True
        if ms.get("fixed_wide_count", 0) > 0:
            fixed_wide_pages.append(ps["url"])

    # Mobile booking accessibility
    if booking_type == "platform":
        if booking_on_homepage:
            booking_mobile_accessible = True
            booking_mobile_detail = (
                f"{booking_platform} booking link present on homepage — accessible on mobile."
            )
        else:
            booking_mobile_accessible = False
            booking_mobile_detail = (
                f"{booking_platform} booking link not found on homepage — "
                "may be buried or hidden behind a desktop-only menu."
            )
    elif booking_type == "form":
        booking_mobile_accessible = True
        booking_mobile_detail = "Contact form detected — accessible on mobile but high friction."
    elif booking_type == "phone_only":
        booking_mobile_accessible = True
        booking_mobile_detail = "Phone-only booking — tap-to-call is mobile-friendly."
    else:
        booking_mobile_accessible = False
        booking_mobile_detail = "No booking system detected — patients on mobile have no way to book."

    # Build findings list
    findings = []

    if not homepage_has_viewport:
        if any_page_has_viewport:
            findings.append(
                "Homepage is missing the viewport meta tag — site is not configured for mobile "
                "on its most important page. Viewport found on inner pages only."
            )
        else:
            findings.append(
                "No viewport meta tag found on any page — site is not configured for mobile devices."
            )
    else:
        findings.append("Viewport meta tag present on homepage — site is configured for mobile.")

    if any_page_has_media_queries:
        findings.append(
            "Responsive CSS detected (media queries present) — layout likely adapts to mobile screen sizes."
        )
    else:
        findings.append(
            "No CSS media queries detected — layout may not adapt to mobile screens. "
            "Site may appear as a scaled-down desktop version on phones."
        )

    if any_page_has_mobile_nav:
        findings.append(
            "Mobile navigation pattern detected (hamburger/toggle menu) — mobile navigation is present."
        )
    else:
        findings.append(
            "No mobile navigation pattern detected — patients on mobile may struggle to navigate the site."
        )

    findings.append(booking_mobile_detail)

    # Speed / weight findings
    if total_imgs > 30:
        findings.append(
            f"{total_imgs} images found across all pages — high image count may slow mobile load times."
        )
    elif total_imgs > 0:
        findings.append(f"{total_imgs} total images across all pages — reasonable image count.")

    if total_imgs_missing_dims > 5:
        findings.append(
            f"{total_imgs_missing_dims} images missing width/height attributes — "
            "may cause layout shift (CLS) on mobile."
        )

    if max_render_blocking > 4:
        findings.append(
            f"Up to {max_render_blocking} render-blocking scripts detected (missing async/defer) — "
            "may delay initial page render on mobile."
        )

    if heavy_pages:
        size_kb = max_html_size // 1024
        findings.append(
            f"{len(heavy_pages)} page(s) exceed 500KB HTML ({size_kb}KB max) — "
            "may load slowly on mobile networks."
        )

    if small_font_found:
        findings.append(
            "Font sizes below 14px detected in inline styles — may be difficult to read on small screens."
        )

    if small_tap_found:
        findings.append(
            "Small tap targets detected (links/buttons under 44px) — may be hard to tap accurately on mobile."
        )

    if fixed_wide_pages:
        findings.append(
            f"Fixed-width elements wider than 400px detected in inline styles — "
            "may cause horizontal scrolling on mobile."
        )

    return {
        "homepage_has_viewport": homepage_has_viewport,
        "any_page_has_viewport": any_page_has_viewport,
        "has_media_queries": any_page_has_media_queries,
        "has_mobile_nav": any_page_has_mobile_nav,
        "booking_mobile_accessible": booking_mobile_accessible,
        "booking_mobile_detail": booking_mobile_detail,
        "total_imgs": total_imgs,
        "total_imgs_missing_dims": total_imgs_missing_dims,
        "max_render_blocking_scripts": max_render_blocking,
        "max_html_size_bytes": max_html_size,
        "heavy_pages": heavy_pages,
        "small_font_found": small_font_found,
        "small_tap_found": small_tap_found,
        "fixed_wide_pages": fixed_wide_pages,
        "findings": findings,
    }


# ===========================================================================
# AGGREGATE SIGNALS ACROSS ALL PAGES
# ===========================================================================

def aggregate_signals(page_signals: list[dict], homepage_url: str) -> dict:
    """
    Combine per-page signals into site-wide totals.
    Gives extra weight to homepage and services pages for scoring.
    """
    total_booking = 0
    total_review = 0
    all_services = set()
    homepage_services = set()
    services_page_services = set()
    contact_any = {"phone": False, "email": False, "address": False}
    contact_phone_sample = None
    contact_email_sample = None
    insurance_any = False
    insurance_on_key_page = False
    all_locations = set()
    homepage_locations = set()
    homepage_title = ""
    booking_on_homepage = 0
    # Booking system aggregation
    best_booking_type = "none"
    booking_platform_name = None
    booking_platform_on_homepage = False   # homepage itself links to a platform
    has_dedicated_booking_page = False     # /book or /appointment page has a platform
    booking_cta_on_homepage = False        # homepage has booking CTA keywords
    _booking_rank = {"platform": 4, "internal_booking": 3.5, "form": 3, "phone_only": 2, "none": 1}
    # Contact quality aggregation
    has_clickable_phone = False
    has_hours = False
    contact_in_header_footer = False
    # Trust / review aggregation
    has_review_widget = False
    has_testimonial_content = False
    max_testimonial_count = 0
    has_star_rating = False
    all_review_platforms = set()
    has_gbp_link = False
    has_credentials = False
    has_professional_assoc = False
    has_years_in_practice = False
    best_rating_value = None
    best_review_count = None
    most_recent_review_date = None
    has_misleading_review_claim = False  # Flag if claimed rating ≠ actual rating
    # Team credibility aggregation
    best_team_member_count = 0
    best_credentialed_count = 0
    has_detailed_team_bios = False
    # Local SEO aggregation
    city_in_title = False
    neighbourhood_mentioned = False
    google_map_on_contact = False
    has_local_schema = False
    # Meta description aggregation
    pages_with_meta_desc = 0
    pages_with_proper_meta_desc = 0
    homepage_has_meta_desc = False
    # Image alt text aggregation
    total_images = 0
    total_images_missing_alt = 0
    # PageSpeed aggregation
    best_pagespeed_score = None
    homepage_pagespeed = None
    # Insurance depth aggregation
    best_insurance_specificity = "none"
    insurance_providers_found = set()
    direct_billing_mentioned = False
    insurance_on_homepage = False
    _ins_rank = {"none": 0, "vague": 1, "moderate": 2, "strong": 3}

    homepage_norm = normalize_url(homepage_url)

    for ps in page_signals:
        url_norm = normalize_url(ps["url"])
        path = urlparse(url_norm).path.lower()
        is_homepage = (url_norm == homepage_norm)
        is_services = any(kw in path for kw in ("service", "treatment", "condition"))
        is_key_page = is_homepage or is_services or "book" in path or "appointment" in path

        total_booking += ps["booking_keyword_count"]
        total_review += ps["review_keyword_count"]

        for svc in ps["service_categories"]:
            all_services.add(svc)
            if is_homepage:
                homepage_services.add(svc)
            if is_services:
                services_page_services.add(svc)

        if ps["contact"]["phone"]:
            contact_any["phone"] = True
            contact_phone_sample = ps["contact"].get("phone_sample")
        if ps["contact"]["email"]:
            contact_any["email"] = True
            contact_email_sample = ps["contact"].get("email_sample")
        if ps["contact"]["address"]:
            contact_any["address"] = True

        if ps["insurance_mentioned"]:
            insurance_any = True
            if is_key_page:
                insurance_on_key_page = True

        ins_depth = ps.get("insurance_depth", {})
        ins_spec = ins_depth.get("specificity", "none")
        if _ins_rank.get(ins_spec, 0) > _ins_rank.get(best_insurance_specificity, 0):
            best_insurance_specificity = ins_spec
        for p in ins_depth.get("providers_found", []):
            insurance_providers_found.add(p)
        if ins_depth.get("direct_billing"):
            direct_billing_mentioned = True
        # Require 'strong' specificity on homepage (providers named + direct billing)
        # to qualify for the 9/10 insurance tier. 'moderate' (direct billing only)
        # is not sufficient — providers must be visible to patients on the homepage.
        if is_homepage and ins_spec == "strong":
            insurance_on_homepage = True

        for loc in ps["locations"]:
            all_locations.add(loc)
            if is_homepage:
                homepage_locations.add(loc)

        # Contact quality aggregation
        cq = ps.get("contact_quality", {})
        if cq.get("clickable_phone"):
            has_clickable_phone = True
        if cq.get("has_hours"):
            has_hours = True
        if cq.get("contact_in_header_footer"):
            contact_in_header_footer = True

        # Trust signals aggregation
        ts = ps.get("trust_signals", {})
        if ts.get("has_review_widget"):
            has_review_widget = True
        if ts.get("has_testimonial_content"):
            has_testimonial_content = True
        max_testimonial_count = max(max_testimonial_count, ts.get("testimonial_count", 0))
        if ts.get("has_star_rating"):
            has_star_rating = True
        for platform in ts.get("review_platforms_linked", []):
            all_review_platforms.add(platform)
            if platform == "Google Business":
                has_gbp_link = True
        if ts.get("has_credentials"):
            has_credentials = True
        if ts.get("has_professional_assoc"):
            has_professional_assoc = True
        if ts.get("has_years_in_practice"):
            has_years_in_practice = True

        # Aggregate review schema metrics (Google rating + count + recency)
        if ts.get("rating_value") is not None:
            if best_rating_value is None or ts.get("rating_value") > best_rating_value:
                best_rating_value = ts.get("rating_value")
        if ts.get("review_count") is not None:
            if best_review_count is None or ts.get("review_count") > best_review_count:
                best_review_count = ts.get("review_count")
        if ts.get("most_recent_date"):
            if most_recent_review_date is None or ts.get("most_recent_date") > most_recent_review_date:
                most_recent_review_date = ts.get("most_recent_date")
        # Track if any page has a misleading review claim
        if ts.get("has_misleading_claim"):
            has_misleading_review_claim = True

        # Team credibility aggregation
        tc = ps.get("team_credibility", {})
        best_team_member_count = max(best_team_member_count, tc.get("team_member_count", 0))
        best_credentialed_count = max(best_credentialed_count, tc.get("credentialed_members", 0))
        if tc.get("has_detailed_bios"):
            has_detailed_team_bios = True

        # Local SEO signals
        if ps.get("local_schema"):
            has_local_schema = True
        if ps.get("map_embed") and "contact" in path:
            google_map_on_contact = True
        if (is_homepage or "contact" in path) and ps.get("neighbourhood_detected"):
            neighbourhood_mentioned = True

        if is_homepage:
            homepage_title = ps.get("title", "")
            booking_on_homepage = ps["booking_keyword_count"]
            booking_cta_on_homepage = ps["booking_keyword_count"] > 0
            if ps.get("booking_system", {}).get("type") == "platform":
                booking_platform_on_homepage = True

        # Track best booking system found across all pages
        bs = ps.get("booking_system", {})
        bs_type = bs.get("type", "none")
        if _booking_rank.get(bs_type, 0) > _booking_rank.get(best_booking_type, 0):
            best_booking_type = bs_type
            booking_platform_name = bs.get("platform_name")

        # Dedicated booking page: path contains /book or /appointment AND has a platform
        if any(kw in path for kw in ("/book", "/appointment")) and bs_type == "platform":
            has_dedicated_booking_page = True

        # Meta description aggregation
        meta_desc = ps.get("meta_descriptions", {})
        if meta_desc.get("has_description"):
            pages_with_meta_desc += 1
            if meta_desc.get("status") == "ok":
                pages_with_proper_meta_desc += 1
        if is_homepage and meta_desc.get("has_description"):
            homepage_has_meta_desc = True

        # Image alt text aggregation
        ms = ps.get("mobile_signals", {})
        img_count = ms.get("img_count", 0)
        imgs_missing_alt = ms.get("imgs_missing_alt", 0)
        total_images += img_count
        total_images_missing_alt += imgs_missing_alt

        # PageSpeed aggregation
        ps_result = ps.get("pagespeed", {})
        if ps_result.get("mobile_score") is not None:
            score = ps_result.get("mobile_score")
            if best_pagespeed_score is None or score > best_pagespeed_score:
                best_pagespeed_score = score
            if is_homepage:
                homepage_pagespeed = score

    # City-in-title: check homepage title against known cities and neighbourhood terms
    title_lower = homepage_title.lower()
    city_in_title = (
        any(city in title_lower for city in CANADIAN_CITIES)
        or any(term in title_lower for term in NEIGHBOURHOOD_TERMS)
    )

    # Services for scoring: use homepage + services page union (avoid FAQ/contact inflation)
    scoring_services = homepage_services | services_page_services

    # Service presentation quality assessment
    service_presentation = assess_service_presentation(page_signals, homepage_url)

    # Mobile readiness assessment
    mobile_readiness = assess_mobile_readiness(
        page_signals=page_signals,
        homepage_url=homepage_url,
        booking_type=best_booking_type,
        booking_platform=booking_platform_name,
        booking_on_homepage=booking_platform_on_homepage,
    )

    return {
        "total_booking_count": total_booking,
        "booking_on_homepage": booking_on_homepage,
        "booking_system_type": best_booking_type,
        "booking_platform_name": booking_platform_name,
        "booking_platform_on_homepage": booking_platform_on_homepage,
        "has_dedicated_booking_page": has_dedicated_booking_page,
        "booking_cta_on_homepage": booking_cta_on_homepage,
        "total_review_count": total_review,
        "all_service_categories": sorted(all_services),
        "scoring_service_categories": sorted(scoring_services),
        "service_presentation": service_presentation,
        "contact": {**contact_any, "phone_sample": contact_phone_sample, "email_sample": contact_email_sample},
        "has_clickable_phone": has_clickable_phone,
        "has_hours": has_hours,
        "contact_in_header_footer": contact_in_header_footer,
        "insurance_any": insurance_any,
        "insurance_on_key_page": insurance_on_key_page,
        "insurance_specificity": best_insurance_specificity,
        "insurance_providers_found": sorted(insurance_providers_found),
        "direct_billing_mentioned": direct_billing_mentioned,
        "insurance_on_homepage": insurance_on_homepage,
        "has_review_widget": has_review_widget,
        "has_testimonial_content": has_testimonial_content,
        "max_testimonial_count": max_testimonial_count,
        "has_star_rating": has_star_rating,
        "review_platforms_linked": sorted(all_review_platforms),
        "review_platform_count": len(all_review_platforms),
        "has_gbp_link": has_gbp_link,
        "best_rating_value": best_rating_value,
        "best_review_count": best_review_count,
        "most_recent_review_date": most_recent_review_date,
        "has_misleading_review_claim": has_misleading_review_claim,
        "best_team_member_count": best_team_member_count,
        "best_credentialed_count": best_credentialed_count,
        "has_detailed_team_bios": has_detailed_team_bios,
        "has_credentials": has_credentials,
        "has_professional_assoc": has_professional_assoc,
        "has_years_in_practice": has_years_in_practice,
        "all_locations": sorted(all_locations),
        "homepage_locations": sorted(homepage_locations),
        "homepage_title": homepage_title,
        "city_in_title": city_in_title,
        "neighbourhood_mentioned": neighbourhood_mentioned,
        "google_map_on_contact": google_map_on_contact,
        "has_local_schema": has_local_schema,
        "pages_with_meta_desc": pages_with_meta_desc,
        "pages_with_proper_meta_desc": pages_with_proper_meta_desc,
        "homepage_has_meta_desc": homepage_has_meta_desc,
        "total_images": total_images,
        "total_images_missing_alt": total_images_missing_alt,
        "alt_coverage_pct": round(((total_images - total_images_missing_alt) / total_images * 100), 1) if total_images > 0 else 100,
        "best_pagespeed_score": best_pagespeed_score,
        "homepage_pagespeed": homepage_pagespeed,
        "mobile_readiness": mobile_readiness,
    }


# ===========================================================================
# DESIGN & ACCESSIBILITY ASSESSMENT (non-scored findings)
# ===========================================================================

def assess_design_quality(agg: dict, page_signals: list[dict]) -> dict:
    """
    Assess design and accessibility without scoring.
    Returns flags and recommendations for design improvements.
    """
    findings = []

    # --- Image optimization ---
    total_images = agg.get("total_images", 0)
    alt_coverage = agg.get("alt_coverage_pct", 100)

    if total_images > 80:
        findings.append(f"⚠️  Visual clutter: {total_images} images across all pages — consider optimization to reduce load time.")
    elif total_images > 0 and alt_coverage < 80:
        findings.append(f"⚠️  Accessibility: {int(agg.get('total_images_missing_alt', 0))} images missing alt text ({100-alt_coverage:.0f}% coverage) — hurts SEO and accessibility.")
    elif total_images == 0:
        findings.append("ℹ️  No images detected — text-heavy or missing visual content.")

    # --- Mobile readiness ---
    mobile = agg.get("mobile_readiness", {})
    font_issues = mobile.get("small_tap_found", False)
    if font_issues:
        findings.append("⚠️  Typography: Font sizes below 14px detected — difficult to read on mobile devices.")

    render_blockers = mobile.get("render_blockers", 0)
    if render_blockers >= 5:
        findings.append(f"⚠️  Performance: {render_blockers} render-blocking scripts detected — may delay page load on slow connections.")

    large_pages = mobile.get("pages_over_500kb", 0)
    if large_pages > 0:
        findings.append(f"⚠️  Performance: {large_pages} page(s) exceed 500KB — slow on mobile networks.")

    # Check mobile readiness based on actual viewport detection
    has_mobile_viewport = agg.get("mobile_readiness", {}).get("any_page_has_viewport", False)
    has_media_queries = agg.get("mobile_readiness", {}).get("has_media_queries", False)
    if has_mobile_viewport and has_media_queries:
        findings.append("✓ Mobile responsive: Viewport meta tag and responsive CSS detected.")
    elif has_mobile_viewport:
        findings.append("✓ Mobile viewport: Configured for mobile devices.")
    else:
        findings.append("⚠️  Not mobile-responsive: Missing viewport meta tag — site may not adapt to mobile screen sizes.")

    # --- Navigation ---
    internal_link_count = sum(len(ps.get("internal_links", [])) for ps in page_signals)
    if internal_link_count > 50:
        findings.append(f"⚠️  Navigation complexity: {internal_link_count} internal links detected — site structure may be confusing.")
    elif internal_link_count < 5:
        findings.append("⚠️  Sparse navigation: Very few internal links — patients may not find important pages.")

    # --- Meta descriptions (SEO + UX signal) ---
    pages_with_proper_meta = agg.get("pages_with_proper_meta_desc", 0)
    total_pages_tracked = agg.get("pages_with_meta_desc", 0)
    if total_pages_tracked > 0 and pages_with_proper_meta < total_pages_tracked * 0.5:
        findings.append(f"⚠️  SEO/UX: Only {pages_with_proper_meta}/{total_pages_tracked} pages have proper meta descriptions — limits Google snippet quality.")

    # --- Accessibility signals ---
    has_heading_structure = any(ps.get("has_h1") for ps in page_signals)
    if not has_heading_structure:
        findings.append("⚠️  Accessibility: No H1 headings detected — poor document structure for screen readers.")

    # --- Performance (if PageSpeed available) ---
    pagespeed = agg.get("homepage_pagespeed", {})
    if pagespeed and "mobile_score" in pagespeed:
        mobile_score = pagespeed.get("mobile_score")
        if mobile_score < 50:
            findings.append(f"⚠️  Mobile Performance: PageSpeed score is {mobile_score}/100 — poor user experience on mobile.")
        elif mobile_score < 75:
            findings.append(f"ℹ️  Mobile Performance: PageSpeed score is {mobile_score}/100 — room for improvement.")
        else:
            findings.append(f"✓ Mobile Performance: PageSpeed score is {mobile_score}/100 — good performance.")

    # --- Trust signals in design ---
    has_credentials = agg.get("has_credentials", False)
    if has_credentials:
        findings.append("✓ Credibility: Professional credentials displayed — builds trust.")

    # Default: if no findings, add positive note
    if not findings:
        findings.append("ℹ️  No major design/accessibility issues detected from automated analysis.")

    return {
        "design_flags": findings,
    }


# ===========================================================================
# SCORING
# ===========================================================================

def score_site(agg: dict) -> dict:
    """
    Score the site across 6 categories, each out of 10.
    Rules are simple, deterministic, and explainable.
    Each category that has been rewritten to quality-based tiers also
    populates a findings list explaining the score.
    """
    scores = {}
    findings = {}   # keyed by category name, populated for rewritten categories

    # ------------------------------------------------------------------
    # 1. LOCAL RELEVANCE (out of 10) — quality-based tiers
    # Tier logic matches plan-scoring-rewrite.md:
    #   0     = no location signals at all
    #   1-2   = city on inner pages only, not in title or homepage
    #   3-4   = city on homepage but weak SEO structure (no title OR no address)
    #   5     = city in title + homepage + address (base local SEO covered)
    #   6     = above + neighbourhood OR Google Map
    #   7     = above + neighbourhood AND Google Map (no schema)
    #   8     = LocalBusiness schema present (without neighbourhood + map)
    #   9     = schema + neighbourhood or Google Map
    # ------------------------------------------------------------------
    city_on_homepage  = bool(agg["homepage_locations"])
    city_anywhere     = bool(agg["all_locations"])
    city_in_title     = agg.get("city_in_title", False)
    has_address       = agg["contact"]["address"]
    neighbourhood     = agg.get("neighbourhood_mentioned", False)
    google_map        = agg.get("google_map_on_contact", False)
    has_schema        = agg.get("has_local_schema", False)
    loc_findings      = []

    if not city_anywhere:
        loc_score = 0
        loc_findings.append("No city or location signals detected on any page.")
    elif not city_on_homepage:
        loc_score = 2
        loc_findings.append(
            f"City detected ({', '.join(agg['all_locations'])}) only on inner pages — "
            "not on homepage and not in title tag."
        )
    elif not city_in_title and not has_address:
        loc_score = 3
        loc_findings.append(
            f"City on homepage ({', '.join(agg['homepage_locations'])}) but not in title tag and no address found."
        )
    elif not city_in_title or not has_address:
        loc_score = 4
        if not city_in_title:
            loc_findings.append(
                f"City on homepage and address present, but city not found in title tag (title: \"{agg['homepage_title']}\")."
            )
        else:
            loc_findings.append(
                f"City in title tag and on homepage, but no physical address detected."
            )
    else:
        # Base tier: city in title + homepage + address
        if has_schema:
            loc_score = 9 if (neighbourhood or google_map) else 8
            loc_findings.append("LocalBusiness schema markup detected — strong local SEO signal.")
        elif neighbourhood and google_map:
            loc_score = 7
            loc_findings.append("Neighbourhood targeting and Google Map embed both detected.")
        elif neighbourhood or google_map:
            loc_score = 6
            if neighbourhood:
                loc_findings.append("Neighbourhood/area targeting detected on homepage or contact page.")
            if google_map:
                loc_findings.append("Google Map embedded on contact page.")
        else:
            loc_score = 5
            loc_findings.append(
                "City in title tag, on homepage, and address present — "
                "missing neighbourhood targeting, Google Map, or schema markup."
            )
        loc_findings.insert(0,
            f"City '{', '.join(agg['homepage_locations'])}' in title and homepage. "
            f"Address present: {has_address}."
        )

    scores["Local Relevance"] = loc_score
    findings["Local Relevance"] = loc_findings

    # ------------------------------------------------------------------
    # 2. SERVICES VISIBILITY (out of 10) — quality-based tiers
    # Tier logic matches plan-scoring-rewrite.md:
    #   0     = no services mentioned anywhere
    #   1-2   = 1-2 categories, no services page
    #   3-4   = services found but not on homepage, OR services page with < 3 cats
    #   5-6   = services page 3+ cats + on homepage, no descriptions or subpages
    #   7-8   = services page with descriptions + 5+ cats on homepage + some subpages
    #   9-10  = comprehensive: descriptions + 3+ subpages + 5+ cats + clear homepage section
    # ------------------------------------------------------------------
    svc = agg.get("service_presentation", {})
    svc_count       = svc.get("service_count", len(agg["scoring_service_categories"]))
    has_svc_page    = svc.get("has_services_page", False)
    has_home_svcs   = svc.get("has_homepage_services", False)
    has_desc        = svc.get("services_have_descriptions", False)
    has_subpages    = svc.get("has_dedicated_subpages", False)
    n_subpages      = len(svc.get("subpages_found", []))
    svc_findings    = list(svc.get("details", []))

    if svc_count == 0:
        svc_score = 0
        svc_findings.insert(0, "No service categories detected on any page.")
    elif svc_count <= 2 and not has_svc_page:
        svc_score = 2
        svc_findings.insert(0, f"Only {svc_count} service category(ies) detected — no dedicated services page.")
    elif not has_home_svcs:
        # Services exist but don't appear on the homepage
        svc_score = 3 if svc_count < 3 else 4
        svc_findings.insert(0, "Services not detected on homepage — patients may not immediately see what's offered.")
    elif has_desc and svc_count >= 5 and has_subpages and n_subpages >= 3:
        svc_score = 9
        svc_findings.insert(0, "Comprehensive service presentation: descriptions, dedicated sub-pages, and homepage coverage.")
    elif has_desc and svc_count >= 5 and has_subpages:
        svc_score = 8
        svc_findings.insert(0, "Strong service presentation: descriptions and dedicated sub-pages detected.")
    elif has_desc and svc_count >= 5:
        svc_score = 7
        svc_findings.insert(0, "Services page has descriptions and 5+ categories on homepage — missing dedicated sub-pages.")
    elif has_desc:
        svc_score = 6
        svc_findings.insert(0, "Services page appears to have descriptions, but fewer than 5 categories detected on key pages.")
    elif has_svc_page and svc_count >= 5:
        svc_score = 6
        svc_findings.insert(0, "Services page exists with 5+ categories on homepage, but appears to be a list of names only — no descriptions.")
    elif has_svc_page and svc_count >= 3:
        svc_score = 5
        svc_findings.insert(0, "Services page exists with 3+ categories — appears to be a name list without descriptions or sub-pages.")
    else:
        svc_score = 4
        svc_findings.insert(0, "Services mentioned on homepage but limited — no services page or fewer than 3 categories.")

    scores["Services Visibility"] = svc_score
    findings["Services Visibility"] = svc_findings

    # ------------------------------------------------------------------
    # 3. BOOKING CONVERSION (out of 10) — quality-based tiers
    # Tier logic matches plan-scoring-rewrite.md:
    #   0     = no booking signals at all
    #   1-2   = phone-only
    #   3-4   = contact form (medium-high friction)
    #   5-6   = platform found but buried, OR strong CTA but form-only
    #   7-8   = platform + homepage CTA
    #   9-10  = platform + homepage CTA + dedicated booking page
    # ------------------------------------------------------------------
    booking_type = agg.get("booking_system_type", "none")
    platform_name = agg.get("booking_platform_name")
    platform_on_homepage = agg.get("booking_platform_on_homepage", False)
    cta_on_homepage = agg.get("booking_cta_on_homepage", False)
    has_dedicated = agg.get("has_dedicated_booking_page", False)
    book_findings = []

    if booking_type == "platform":
        if platform_on_homepage and has_dedicated:
            book_score = 9
            book_findings.append(
                f"{platform_name} booking platform detected — homepage CTA present and dedicated booking page found. Low friction."
            )
        elif platform_on_homepage:
            book_score = 7
            book_findings.append(
                f"{platform_name} booking platform detected with homepage CTA. No dedicated booking page found."
            )
        elif has_dedicated:
            book_score = 7
            book_findings.append(
                f"{platform_name} booking platform found on dedicated booking page, but not linked from the homepage."
            )
        else:
            book_score = 5
            book_findings.append(
                f"{platform_name} booking platform detected but buried — not on homepage or a dedicated booking page."
            )
        if not cta_on_homepage:
            book_findings.append("No booking CTA (e.g. 'Book Now', 'Book Online') detected on homepage.")
    elif booking_type == "form":
        if cta_on_homepage:
            book_score = 4
            book_findings.append(
                "Booking CTA present on homepage, but it leads to a contact form — patients submit and wait for a callback."
            )
            book_findings.append("No real-time online booking system found.")
        else:
            book_score = 3
            book_findings.append(
                "Contact form detected — patients must submit a form and wait for a callback to schedule."
            )
            book_findings.append("No booking CTA found on homepage. No real-time booking system detected.")
    elif booking_type == "phone_only":
        book_score = 2
        book_findings.append(
            "Phone-only booking detected — patients must call to schedule. No online booking option available."
        )
        if cta_on_homepage:
            book_findings.append("Booking language present on homepage but directs patients to phone only.")
    else:  # none
        book_score = 0
        book_findings.append("No booking system detected on any page. No booking CTA found.")

    scores["Booking Conversion"] = book_score
    findings["Booking Conversion"] = book_findings

    # ------------------------------------------------------------------
    # 4. TRUST / REVIEWS (out of 10) — quality-based tiers
    # NEW: Incorporates Google review count + rating + recency + multi-platform presence
    # Tier logic:
    #   0   = no review signals anywhere
    #   1-2 = review language only (no actual content, ratings, or platforms)
    #   3-4 = testimonials or widget or single platform, but weak corroboration
    #   5-6 = testimonials + widget OR 2+ platforms OR vague Google rating
    #   7-8 = substantial Google reviews (10-40 count) at good rating (4.5+) OR widget + 2+ platforms
    #   9-10= 40+ Google reviews at 4.5+ rating OR 3+ platforms + recent activity + credentials
    # ------------------------------------------------------------------
    has_widget      = agg.get("has_review_widget", False)
    has_testim      = agg.get("has_testimonial_content", False)
    testim_count    = agg.get("max_testimonial_count", 0)
    has_stars       = agg.get("has_star_rating", False)
    platforms       = agg.get("review_platforms_linked", [])
    review_platform_count = agg.get("review_platform_count", 0)
    has_gbp         = agg.get("has_gbp_link", False)
    has_creds       = agg.get("has_credentials", False)
    has_years       = agg.get("has_years_in_practice", False)
    rev_keywords    = agg.get("total_review_count", 0)
    rating_value    = agg.get("best_rating_value")
    review_count    = agg.get("best_review_count")
    most_recent_date = agg.get("most_recent_review_date")
    rev_findings    = []

    # Helper: check if review is recent (within 180 days)
    def is_recent_review(date_str):
        if not date_str:
            return False
        try:
            from datetime import datetime, timedelta
            review_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return (datetime.now(review_date.tzinfo) - review_date).days < 180
        except:
            return False

    recent_reviews = is_recent_review(most_recent_date)

    # --- Scoring Logic ---
    if not has_testim and not has_widget and not has_stars and not platforms and review_count is None and rev_keywords == 0:
        # TIER 0: No signals at all
        rev_score = 0
        rev_findings.append("No review, testimonial, or trust signals found anywhere on the site.")

    elif review_count is not None and review_count >= 30 and rating_value is not None and rating_value >= 4.5:
        # TIER 9-10: Strong Google review presence (30+ reviews, 4.5+ rating)
        if review_platform_count >= 3 and recent_reviews and (has_creds or has_years):
            rev_score = 10
            rev_findings.append(
                f"Strong trust signals: {review_count} Google reviews at {rating_value}★, "
                f"visible on {review_platform_count} platforms, recent activity, professional credentials."
            )
        elif review_platform_count >= 2 or recent_reviews:
            rev_score = 9
            rev_findings.append(
                f"Strong Google review presence: {review_count} reviews at {rating_value}★"
                + (f", recent activity within 180 days." if recent_reviews else f" across {review_platform_count} platforms.")
            )
        else:
            rev_score = 8
            rev_findings.append(f"{review_count} Google reviews at {rating_value}★ — substantial social proof.")

    elif review_count is not None and review_count >= 15 and rating_value is not None and rating_value >= 4.0:
        # TIER 7-8: Moderate Google review presence (15-40 reviews, 4.0+ rating)
        if review_platform_count >= 2:
            rev_score = 8
            rev_findings.append(f"{review_count} Google reviews at {rating_value}★ across {review_platform_count} platforms — strong multi-platform trust.")
        else:
            rev_score = 7
            rev_findings.append(f"{review_count} Google reviews at {rating_value}★ — good social proof established.")
        if recent_reviews:
            rev_findings.append("Recent reviews within last 6 months — ongoing patient satisfaction.")

    elif review_count is not None and review_count >= 5 and rating_value is not None and rating_value >= 4.0:
        # TIER 5-6: Growing Google review presence (5-15 reviews, 4.0+ rating)
        if has_widget or review_platform_count >= 2:
            rev_score = 6
            rev_findings.append(f"{review_count} Google reviews at {rating_value}★ with multi-platform presence — solid foundation for trust.")
        else:
            rev_score = 5
            rev_findings.append(f"{review_count} Google reviews at {rating_value}★ — early social proof, needs continued development.")

    elif has_widget:
        # TIER 7-8: Embedded review widget (regardless of count)
        if has_gbp and (has_creds or has_years):
            rev_score = 9
            rev_findings.append(
                "Embedded review widget with Google Business Profile link and professional credentials — demonstrates trust investment."
            )
        elif has_gbp or (has_stars and has_testim):
            rev_score = 8
            rev_findings.append(
                "Embedded review widget" +
                (", linked to Google Business Profile." if has_gbp else " with visible star ratings and testimonials.")
            )
        else:
            rev_score = 7
            rev_findings.append("Embedded review widget detected — auto-updating social proof.")

    elif review_platform_count >= 3:
        # TIER 7-8: Multi-platform presence (3+ platforms)
        if review_count is not None:
            rev_score = 7
            rev_findings.append(f"Active on {review_platform_count} review platforms ({', '.join(platforms)}) — strong multi-platform strategy.")
        else:
            rev_score = 6
            rev_findings.append(f"Present on {review_platform_count} review platforms — diversified trust signals.")

    elif review_platform_count >= 2 and (has_stars or has_testim):
        # TIER 6: Two platforms + additional trust signals
        rev_score = 6
        rev_findings.append(
            f"Multi-platform presence ({', '.join(platforms)}) with " +
            ("star ratings" if has_stars else "testimonial content") + " — solid trust foundation."
        )

    elif has_testim and has_stars and review_platform_count >= 1:
        # TIER 5-6: Testimonials + stars + at least one platform
        rev_score = 6
        rev_findings.append(
            f"Testimonials, star rating, and link to {platforms[0] if platforms else 'review platform'} — strong non-embedded trust signals."
        )

    elif has_testim and (has_stars or review_platform_count >= 1):
        # TIER 5: Testimonials + stars OR testimonials + one platform
        rev_score = 5
        if has_stars:
            rev_findings.append("Testimonial content with star rating visible — good trust foundation.")
        if review_platform_count >= 1:
            rev_findings.append(f"Link to {platforms[0]} — encourages external verification.")

    elif has_testim and testim_count >= 3:
        # TIER 4: Multiple testimonials but no other signals
        rev_score = 4
        rev_findings.append(f"{testim_count} testimonials displayed — provides some voice but lacks external verification.")

    elif has_testim or has_stars or review_platform_count >= 1:
        # TIER 3: Limited signals (one or two weak indicators)
        rev_score = 3
        signals = []
        if has_testim:
            signals.append(f"{testim_count} testimonial(s)")
        if has_stars:
            signals.append("star rating")
        if review_platform_count >= 1:
            signals.append(f"{platforms[0]} link")
        rev_findings.append(f"Limited trust signals: {', '.join(signals).capitalize()} — needs stronger corroboration.")

    else:
        # TIER 2: Only keyword mentions
        rev_score = 2
        rev_findings.append("Review language detected (mentions, links) but no actual testimonial content or current ratings.")

    # --- Supplemental findings ---
    if review_count is not None and review_count < 5:
        rev_findings.append(f"Review volume is low ({review_count} reviews) — building more social proof would strengthen credibility.")
    if most_recent_date and not recent_reviews:
        months_old = "6+ months" if most_recent_date else "unknown"
        rev_findings.append(f"Most recent review appears older than 6 months — implement active review request process.")
    if review_platform_count == 1:
        rev_findings.append("Only present on one review platform — adding 1-2 more would reduce risk of single-platform dependency.")
    if has_creds and rev_score < 9:
        rev_findings.append("Professional credentials detected — reinforces trust.")
    if has_years and rev_score < 9:
        rev_findings.append("Years in practice mentioned — shows stability.")
    if not has_gbp and rev_score >= 5 and review_count is None:
        rev_findings.append("Missing Google Business Profile link — recommend adding for discoverability and reviews.")

    # Schema data freshness note
    if review_count is not None:
        rev_findings.append(
            "NOTE: Review count and rating from website schema markup. "
            "Actual Google Business Profile may show higher numbers if schema hasn't been updated recently. "
            "Verify on Google Maps for most current data."
        )

    # --- CRITICAL: Penalize misleading review claims ---
    has_misleading_claim = agg.get("has_misleading_review_claim", False)
    if has_misleading_claim:
        rev_score = max(1, rev_score - 4)  # Severe penalty for false/inflated claims
        rev_findings.insert(0, "⚠️ CRITICAL: Site displays inaccurate review ratings (claimed vs. actual mismatch). This damages credibility.")

    scores["Trust / Reviews"] = rev_score
    findings["Trust / Reviews"] = rev_findings

    # ------------------------------------------------------------------
    # 5. CONTACT COMPLETENESS (out of 10) — quality-based tiers
    # Tier logic matches plan-scoring-rewrite.md:
    #   0     = no contact information found
    #   1-3   = only one contact method
    #   4-5   = two of three methods (phone/email/address)
    #   6-7   = all three methods present
    #   8-9   = all three + hours displayed + contact in header/footer
    #   10    = all three + hours + header/footer + clickable phone + Google Map
    # ------------------------------------------------------------------
    c               = agg["contact"]
    phone           = c["phone"]
    email           = c["email"]
    address         = c["address"]
    clickable_phone = agg.get("has_clickable_phone", False)
    has_hrs         = agg.get("has_hours", False)
    in_hdr_ftr      = agg.get("contact_in_header_footer", False)
    map_on_contact  = agg.get("google_map_on_contact", False)
    contact_findings = []

    methods_present = [m for m in [("Phone", phone), ("Email", email), ("Address", address)] if m[1]]
    n_methods = len(methods_present)

    if n_methods == 0:
        contact_score = 0
        contact_findings.append("No contact information (phone, email, or address) found on any page.")
    elif n_methods == 1:
        contact_score = 2
        contact_findings.append(f"Only one contact method found: {methods_present[0][0]}.")
        contact_findings.append(
            f"Missing: {', '.join(m for m, _ in [('Phone', phone), ('Email', email), ('Address', address)] if not _)}."
        )
    elif n_methods == 2:
        contact_score = 5 if (phone and address) else 4
        missing = next(m for m, v in [("Phone", phone), ("Email", email), ("Address", address)] if not v)
        contact_findings.append(
            f"{' and '.join(m for m, _ in methods_present)} present — missing {missing}."
        )
    else:
        # All three present — apply quality tiers
        quality_count = sum([has_hrs, in_hdr_ftr])
        if quality_count == 2 and (clickable_phone or map_on_contact):
            contact_score = 10 if (clickable_phone and map_on_contact) else 9
        elif quality_count == 2:
            contact_score = 9
        elif quality_count == 1:
            contact_score = 8
        else:
            contact_score = 6
        contact_findings.append("Phone, email, and address all present.")
        if has_hrs:
            contact_findings.append("Hours of operation displayed.")
        else:
            contact_findings.append("Hours of operation not found — patients may not know when to call.")
        if in_hdr_ftr:
            contact_findings.append("Contact info accessible in site header or footer.")
        else:
            contact_findings.append("Contact info not found in header/footer — patients must navigate to find it.")
        if clickable_phone:
            contact_findings.append("Phone number is clickable (tel: link) — mobile-friendly.")
        if map_on_contact:
            contact_findings.append("Google Map embedded or linked on contact page.")

    scores["Contact Completeness"] = contact_score
    findings["Contact Completeness"] = contact_findings

    # ------------------------------------------------------------------
    # 6. INSURANCE / ACCESSIBILITY (out of 10) — quality-based tiers
    # Tier logic matches plan-scoring-rewrite.md:
    #   0     = no mention anywhere
    #   1-2   = mentioned only in passing on inner/minor pages
    #   3-4   = on a key page but vague (no providers, no direct billing)
    #   5-6   = providers named OR direct billing mentioned (not both)
    #   7-8   = providers named AND direct billing, on a key page
    #   9-10  = strong + prominent placement (homepage) + multiple providers
    # ------------------------------------------------------------------
    ins_spec = agg.get("insurance_specificity", "none")
    ins_providers = agg.get("insurance_providers_found", [])
    ins_direct = agg.get("direct_billing_mentioned", False)
    ins_on_home = agg.get("insurance_on_homepage", False)
    ins_on_key = agg.get("insurance_on_key_page", False)
    ins_findings = []

    if ins_spec == "none":
        ins_score = 0
        ins_findings.append(
            "No mention of insurance or billing found anywhere on the site."
        )
    elif ins_spec == "vague":
        if ins_on_home:
            ins_score = 4
            ins_findings.append(
                "Insurance mentioned on homepage but vague — no providers named, no direct billing explained."
            )
        elif ins_on_key:
            ins_score = 3
            ins_findings.append(
                "Insurance mentioned on a key page but vague — no providers named, no process explained."
            )
        else:
            ins_score = 2
            ins_findings.append(
                "Insurance mentioned only on inner/minor pages — vague, no providers named."
            )
        ins_findings.append(
            "Patients cannot determine from this site whether their plan is accepted."
        )
    elif ins_spec == "moderate":
        if ins_on_home:
            ins_score = 6
        elif ins_on_key:
            ins_score = 5
        else:
            ins_score = 4
        if ins_providers and not ins_direct:
            ins_findings.append(
                f"Providers named ({', '.join(ins_providers)}) but direct billing not explicitly mentioned."
            )
            ins_findings.append(
                "Patients may still need to call to confirm if the clinic will bill directly."
            )
        elif ins_direct and not ins_providers:
            ins_findings.append(
                "Direct billing mentioned but no specific providers listed."
            )
            ins_findings.append(
                "Patients still need to verify whether their plan is covered."
            )
    else:  # strong
        if ins_on_home and len(ins_providers) >= 2:
            ins_score = 9
        elif ins_on_home or len(ins_providers) >= 2:
            ins_score = 8
        elif ins_on_key:
            ins_score = 7
        else:
            ins_score = 6
        ins_findings.append(
            f"Direct billing mentioned and providers named: {', '.join(ins_providers)}."
        )
        if not ins_on_home:
            ins_findings.append(
                "Insurance information not on homepage — adding it there would improve visibility."
            )

    scores["Insurance / Accessibility"] = ins_score
    findings["Insurance / Accessibility"] = ins_findings

    # ------------------------------------------------------------------
    # IMAGE ALT TEXT & META DESCRIPTIONS (supplemental findings)
    # Add to Insurance/Accessibility or Local Relevance section
    # ------------------------------------------------------------------
    alt_coverage = agg.get("alt_coverage_pct", 100)
    pages_with_desc = agg.get("pages_with_proper_meta_desc", 0)
    pages_analyzed = agg.get("pages_with_meta_desc", 0) + (1 if not agg.get("pages_with_meta_desc", 0) else 0)  # at least 1 page

    # Add alt text findings to Insurance/Accessibility findings
    if agg.get("total_images", 0) > 0:
        alt_missing = agg.get("total_images_missing_alt", 0)
        alt_total = agg.get("total_images", 0)
        if alt_coverage < 50:
            findings["Insurance / Accessibility"].append(
                f"Critical: {alt_missing}/{alt_total} images missing alt text ({100-alt_coverage:.0f}% gap). "
                "This affects SEO and accessibility for blind visitors."
            )
        elif alt_coverage < 80:
            findings["Insurance / Accessibility"].append(
                f"Accessibility: {alt_missing}/{alt_total} images missing alt text ({100-alt_coverage:.0f}% gap). "
                "Adding alt descriptions would improve search visibility and accessibility."
            )

    # Add meta description findings to Local Relevance
    if pages_analyzed > 0 and pages_with_desc < pages_analyzed * 0.75:
        findings["Local Relevance"].append(
            f"Meta descriptions: {pages_with_desc}/{pages_analyzed} pages have proper descriptions. "
            f"Missing descriptions mean Google pulls random text for search snippets — bad for CTR."
        )

    # ------------------------------------------------------------------
    # 7. MOBILE READINESS (out of 10) — quality-based tiers
    #
    # Hard caps applied after base scoring:
    #   - Homepage missing viewport tag → max 4
    #   - Booking not accessible on mobile → max 6
    #
    # Tier logic:
    #   0-2   = no viewport tag found on any page
    #   3-4   = viewport found, but no media queries AND no mobile nav
    #   5-6   = viewport + one of (media queries / mobile nav), or both but
    #           booking not accessible / notable issues
    #   7-8   = viewport + media queries + mobile nav + booking accessible,
    #           minor speed risk issues
    #   9-10  = all signals present, booking accessible, no speed risk flags
    # ------------------------------------------------------------------
    mr             = agg.get("mobile_readiness", {})
    homepage_has_vp = mr.get("homepage_has_viewport", False)
    any_vp          = mr.get("any_page_has_viewport", False)
    has_mq          = mr.get("has_media_queries", False)
    has_mob_nav     = mr.get("has_mobile_nav", False)
    book_mobile_ok  = mr.get("booking_mobile_accessible", False)
    max_rbs         = mr.get("max_render_blocking_scripts", 0)
    heavy_pages     = mr.get("heavy_pages", [])
    small_font      = mr.get("small_font_found", False)
    small_tap       = mr.get("small_tap_found", False)
    fixed_wide      = mr.get("fixed_wide_pages", [])
    mob_findings    = list(mr.get("findings", []))

    # Add PageSpeed findings if available
    ps_score = agg.get("best_pagespeed_score")
    if ps_score is not None:
        if ps_score >= 90:
            mob_findings.append(f"Google PageSpeed: Excellent mobile performance ({ps_score}/100).")
        elif ps_score >= 75:
            mob_findings.append(f"Google PageSpeed: Good mobile performance ({ps_score}/100).")
        elif ps_score >= 50:
            mob_findings.append(f"Google PageSpeed: Moderate mobile performance ({ps_score}/100) — patients experience slow load times.")
        else:
            mob_findings.append(f"Google PageSpeed: Poor mobile performance ({ps_score}/100) — site loads too slowly on mobile networks.")

    speed_issues = sum([
        max_rbs > 4,
        bool(heavy_pages),
        small_font,
        small_tap,
        bool(fixed_wide),
    ])

    if not any_vp:
        mob_score = 1   # no responsive configuration at all
    elif not homepage_has_vp:
        mob_score = 3   # viewport on inner pages only — homepage unconfigured
    elif not has_mq and not has_mob_nav:
        mob_score = 4   # viewport only — no responsive layout signals
    elif has_mq and has_mob_nav:
        # Both responsive signals present — base at 7-9
        if speed_issues == 0:
            mob_score = 9
        elif speed_issues == 1:
            mob_score = 8
        else:
            mob_score = 7
    else:
        # One of the two responsive signals present
        mob_score = 6 if speed_issues == 0 else 5

    # Hard cap: homepage missing viewport → max 4
    if not homepage_has_vp:
        mob_score = min(mob_score, 4)
    # Hard cap: booking not accessible on mobile → max 6
    if not book_mobile_ok:
        mob_score = min(mob_score, 6)
    # Hard cap: poor PageSpeed score → max 5 (patients bounce on slow sites)
    if ps_score is not None and ps_score < 50:
        mob_score = min(mob_score, 5)
    elif ps_score is not None and ps_score < 75:
        mob_score = min(mob_score, 7)

    scores["Mobile Readiness"] = mob_score
    findings["Mobile Readiness"] = mob_findings

    total_score = sum(scores.values())
    return {"categories": scores, "findings": findings, "total": total_score, "max": 70}


# ===========================================================================
# PRIORITY ISSUES
# ===========================================================================

ISSUE_EXPLANATIONS = {
    "Local Relevance": (
        "The site does not strongly reinforce local city/service relevance in high-value areas "
        "(title, homepage body, or physical address). This weakens local SEO and trust."
    ),
    "Services Visibility": (
        "Service offerings are not clearly visible on the homepage or services page. "
        "Visitors may not quickly understand what the clinic offers."
    ),
    "Booking Conversion": (
        "Booking signals are limited or weak, which may reduce patient conversion. "
        "Clear 'Book Now' or 'Book Online' calls-to-action should be prominent."
    ),
    "Trust / Reviews": (
        "Testimonials or review signals appear limited. "
        "Social proof is a key trust builder for new patients."
    ),
    "Contact Completeness": (
        "Contact information (phone, address, email) is incomplete or hard to find. "
        "This can frustrate patients and reduce conversions."
    ),
    "Insurance / Accessibility": (
        "Insurance or direct billing information is absent or not prominently displayed. "
        "Many patients filter clinics by billing options before booking."
    ),
    "Mobile Readiness": (
        "The site shows poor mobile optimization. Most patients search for clinics on their phone — "
        "a site that isn't mobile-friendly loses them before they even read a word."
    ),
}

PRIORITY_ISSUE_THRESHOLD = 6   # scores <= this are surfaced as priority issues

def generate_priority_issues(scores: dict) -> list[dict]:
    """
    Return the top 3 weakest scoring categories that score at or below
    PRIORITY_ISSUE_THRESHOLD. Scores of 7-9 are acceptable and not flagged
    as priority issues to avoid misleading problem-framing for strong areas.
    """
    cats = scores["categories"]
    cat_findings = scores.get("findings", {})
    # only include genuinely weak categories
    sorted_cats = sorted(
        [(name, score) for name, score in cats.items() if score <= PRIORITY_ISSUE_THRESHOLD],
        key=lambda x: x[1],
    )
    issues = []
    for name, score in sorted_cats[:3]:
        # Use specific findings if available; fall back to canned explanation
        specific = cat_findings.get(name)
        issues.append({
            "category": name,
            "score": score,
            "max": 10,
            "findings": specific if specific else [ISSUE_EXPLANATIONS.get(name, "Review this area for improvements.")],
        })
    return issues


# ===========================================================================
# REPORT PRINTING
# ===========================================================================

SEP = "=" * 56

def print_section(title: str):
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)


def print_report(
    url: str,
    business_name: str,
    agg: dict,
    scores: dict,
    issues: list[dict],
    page_signals: list[dict],
    analyzed_urls: list[str],
):
    """Print the full structured CLI report."""

    # ------------------------------------------------------------------
    # 1. WEBSITE AUDIT SUMMARY
    # ------------------------------------------------------------------
    print_section("WEBSITE AUDIT SUMMARY")
    print(f"  URL             : {url}")
    print(f"  Business Name   : {business_name}")
    print(f"  Locations Found : {', '.join(agg['all_locations']) or 'None detected'}")
    print(f"  Services Found  : {', '.join(agg['all_service_categories']) or 'None detected'}")
    _bs_type = agg.get("booking_system_type", "none")
    _bs_name = agg.get("booking_platform_name")
    _bs_label = f"platform ({_bs_name})" if _bs_type == "platform" and _bs_name else _bs_type
    print(f"  Booking         : {_bs_label} — {agg['total_booking_count']} keyword signal(s) site-wide")
    print(f"  Reviews/Trust   : {agg['total_review_count']} signal(s) found site-wide")

    c = agg["contact"]
    contact_parts = []
    if c["phone"]:
        contact_parts.append(f"Phone ({c['phone_sample']})" if c["phone_sample"] else "Phone")
    if c["email"]:
        contact_parts.append(f"Email ({c['email_sample']})" if c["email_sample"] else "Email")
    if c["address"]:
        contact_parts.append("Address")
    print(f"  Contact         : {', '.join(contact_parts) or 'None detected'}")
    _ins_spec = agg.get("insurance_specificity", "none")
    _ins_providers = agg.get("insurance_providers_found", [])
    _ins_direct = agg.get("direct_billing_mentioned", False)
    if _ins_spec == "none":
        _ins_label = "Not mentioned"
    elif _ins_spec == "vague":
        _ins_label = "Vague mention — no providers named"
    elif _ins_spec == "moderate":
        _ins_label = f"Partial — {'direct billing' if _ins_direct else 'providers'} mentioned" + (f": {', '.join(_ins_providers)}" if _ins_providers else "")
    else:
        _ins_label = f"Strong — direct billing + {len(_ins_providers)} provider(s): {', '.join(_ins_providers)}"
    print(f"  Insurance/Billing: {_ins_label}")

    # ------------------------------------------------------------------
    # 2. SCORECARD
    # ------------------------------------------------------------------
    print_section("SCORECARD")
    for cat, score in scores["categories"].items():
        bar = "█" * score + "░" * (10 - score)
        print(f"  {cat:<28} {bar}  {score:>2}/10")
    print(f"\n  {'TOTAL':<28}             {scores['total']:>3}/70")

    # ------------------------------------------------------------------
    # 3. PRIORITY ISSUES
    # ------------------------------------------------------------------
    print_section("PRIORITY ISSUES")
    if not issues:
        print("  No major issues detected — all categories scored reasonably well.")
    for i, issue in enumerate(issues, 1):
        print(f"\n  {i}. {issue['category']} ({issue['score']}/{issue['max']})")
        for finding in issue.get("findings", []):
            # word-wrap each finding at ~70 chars
            words = finding.split()
            line = "     - "
            for word in words:
                if len(line) + len(word) + 1 > 75:
                    print(line)
                    line = "       " + word + " "
                else:
                    line += word + " "
            if line.strip():
                print(line)

    # ------------------------------------------------------------------
    # 3b. DESIGN & ACCESSIBILITY FINDINGS
    # ------------------------------------------------------------------
    design_assessment = assess_design_quality(agg, page_signals)
    print_section("DESIGN & ACCESSIBILITY")
    for flag in design_assessment.get("design_flags", []):
        # word-wrap at ~70 chars
        words = flag.split()
        line = "  "
        for word in words:
            if len(line) + len(word) + 1 > 75:
                print(line)
                line = "  " + word + " "
            else:
                line += word + " "
        if line.strip():
            print(line)

    # ------------------------------------------------------------------
    # 4. PAGE SIGNALS
    # ------------------------------------------------------------------
    print_section("PAGE SIGNALS")
    for ps in page_signals:
        print(f"\n  [{ps['url']}]")
        print(f"    Booking signals  : {ps['booking_keyword_count']}")
        bs = ps.get("booking_system", {})
        bs_label = bs.get("type", "unknown")
        if bs.get("platform_name"):
            bs_label += f" ({bs['platform_name']})"
        print(f"    Booking system   : {bs_label}")
        if bs.get("details"):
            print(f"    Booking detail   : {bs['details'][0]}")
        print(f"    Review signals   : {ps['review_keyword_count']}")
        print(f"    Service categories: {', '.join(ps['service_categories']) or 'None'}")
        c = ps["contact"]
        found_contact = []
        if c["phone"]:
            found_contact.append("Phone")
        if c["email"]:
            found_contact.append("Email")
        if c["address"]:
            found_contact.append("Address")
        print(f"    Contact signals  : {', '.join(found_contact) or 'None'}")
        print(f"    Insurance        : {'Yes' if ps['insurance_mentioned'] else 'No'}")
        print(f"    Locations        : {', '.join(ps['locations']) or 'None'}")

    # ------------------------------------------------------------------
    # 5. PAGES ANALYZED
    # ------------------------------------------------------------------
    print_section("PAGES ANALYZED")
    for u in analyzed_urls:
        print(f"  {u}")

    print(f"\n{SEP}\n")


# ===========================================================================
# JSON OUTPUT
# ===========================================================================

OUTPUTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")


def _ensure_outputs_dir() -> str:
    """Create outputs/ directory next to this script if it doesn't exist. Returns path."""
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    return OUTPUTS_DIR


def save_json_report(
    url: str,
    business_name: str,
    agg: dict,
    scores: dict,
    issues: list[dict],
    page_signals: list[dict],
    analyzed_urls: list[str],
    design_assessment: dict,
) -> str:
    """Save the full audit result as a JSON file in outputs/. Returns the file path."""
    out_dir = _ensure_outputs_dir()
    domain = urlparse(url).netloc.lstrip("www.").replace(".", "_")
    filename = os.path.join(out_dir, f"audit_output_{domain}.json")

    output = {
        "url": url,
        "business_name": business_name,
        "audit_date": datetime.now().strftime("%Y-%m-%d"),
        "aggregated_signals": agg,
        "scores": scores,
        "priority_issues": issues,
        "design_and_accessibility": design_assessment,
        "page_signals": page_signals,
        "pages_analyzed": analyzed_urls,
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"  JSON saved to: {filename}")
    return filename


# ===========================================================================
# INTERNAL PDF BRIEF
# ===========================================================================

def _score_color(score: int):
    """Return a reportlab Color for a given score."""
    from reportlab.lib.colors import Color
    if score <= 2:
        return Color(0.80, 0.15, 0.15)   # red
    elif score <= 4:
        return Color(0.85, 0.45, 0.10)   # orange
    elif score <= 6:
        return Color(0.75, 0.60, 0.05)   # amber
    elif score <= 8:
        return Color(0.20, 0.60, 0.25)   # green
    else:
        return Color(0.05, 0.42, 0.15)   # dark green


def _score_label(score: int) -> str:
    if score <= 2:   return "Critical"
    elif score <= 4: return "Weak"
    elif score <= 6: return "Moderate"
    elif score <= 8: return "Good"
    else:            return "Strong"


def save_internal_pdf(data: dict, pdf_path: str) -> None:
    """
    Generate an internal-use audit brief PDF.
    Shows raw scores, all findings (weak AND strong), key facts,
    and suggested services to pitch. NOT for sharing with clinic owners.
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.lib.colors import HexColor, Color
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table,
            TableStyle, HRFlowable,
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    except ImportError:
        print("  [PDF skipped — reportlab not installed. Run: pip install reportlab]")
        return

    scores_dict  = data["scores"]["categories"]
    findings_all = data["scores"].get("findings", {})
    agg          = data["aggregated_signals"]
    issues       = data["priority_issues"]
    total        = data["scores"]["total"]
    max_score    = data["scores"]["max"]

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()

    DARK  = HexColor("#1a1a2e")
    MID   = HexColor("#444455")
    LIGHT = HexColor("#f4f4f8")
    RED   = HexColor("#cc2222")

    styles.add(ParagraphStyle("ITitle",   parent=styles["Title"],   fontSize=20, textColor=DARK,  spaceAfter=2,  alignment=TA_LEFT))
    styles.add(ParagraphStyle("ISub",     parent=styles["Normal"],  fontSize=9,  textColor=MID,   spaceAfter=4))
    styles.add(ParagraphStyle("IWarn",    parent=styles["Normal"],  fontSize=9,  textColor=RED,   spaceAfter=10, alignment=TA_CENTER))
    styles.add(ParagraphStyle("IHead",    parent=styles["Heading2"],fontSize=13, textColor=DARK,  spaceBefore=14, spaceAfter=6))
    styles.add(ParagraphStyle("ISubHead", parent=styles["Normal"],  fontSize=10, textColor=DARK,  spaceBefore=8,  spaceAfter=3))
    styles.add(ParagraphStyle("IBody",    parent=styles["Normal"],  fontSize=9,  textColor=MID,   spaceAfter=3,  leading=13))
    styles.add(ParagraphStyle("IBullet",  parent=styles["Normal"],  fontSize=9,  textColor=MID,   leftIndent=12, spaceAfter=2, leading=13))
    styles.add(ParagraphStyle("IFoot",    parent=styles["Normal"],  fontSize=7,  textColor=HexColor("#aaaaaa"), alignment=TA_CENTER))

    story = []

    # --- HEADER ---
    story.append(Paragraph("Internal Audit Brief", styles["ITitle"]))
    story.append(Paragraph(
        f"{data['business_name']}  ·  {data['url']}  ·  {datetime.now().strftime('%B %d, %Y')}",
        styles["ISub"],
    ))
    story.append(Paragraph("INTERNAL USE ONLY — DO NOT SHARE WITH CLINIC", styles["IWarn"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=DARK))
    story.append(Spacer(1, 8))

    # --- SCORECARD TABLE ---
    story.append(Paragraph("Scorecard", styles["IHead"]))

    tdata = [["Category", "Score", "Status", "Findings (summary)"]]
    for cat, score in scores_dict.items():
        label = _score_label(score)
        cat_findings = findings_all.get(cat, [])
        summary = cat_findings[0][:72] + "…" if cat_findings and len(cat_findings[0]) > 72 else (cat_findings[0] if cat_findings else "—")
        tdata.append([cat, f"{score}/10", label, summary])
    tdata.append(["TOTAL", f"{total}/{max_score}", "", ""])

    col_w = [1.9*inch, 0.55*inch, 0.8*inch, 3.55*inch]
    t = Table(tdata, colWidths=col_w, repeatRows=1)

    ts_cmds = [
        ("BACKGROUND",  (0, 0), (-1, 0),  DARK),
        ("TEXTCOLOR",   (0, 0), (-1, 0),  HexColor("#ffffff")),
        ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0),  9),
        ("FONTNAME",    (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",    (0, 1), (-1, -1), 8),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0,0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("GRID",        (0, 0), (-1, -1), 0.4, HexColor("#cccccc")),
        # Total row
        ("FONTNAME",    (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND",  (0, -1), (-1, -1), LIGHT),
    ]
    for i, (cat, score) in enumerate(scores_dict.items(), start=1):
        col = _score_color(score)
        ts_cmds.append(("TEXTCOLOR", (2, i), (2, i), col))
        ts_cmds.append(("FONTNAME",  (2, i), (2, i), "Helvetica-Bold"))
        if i % 2 == 0:
            ts_cmds.append(("BACKGROUND", (0, i), (-1, i), LIGHT))

    t.setStyle(TableStyle(ts_cmds))
    story.append(t)
    story.append(Spacer(1, 10))

    # --- ALL FINDINGS ---
    story.append(Paragraph("All Findings", styles["IHead"]))

    for cat, score in scores_dict.items():
        col = _score_color(score)
        r, g, b = col.red, col.green, col.blue
        hex_col = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
        story.append(Paragraph(
            f"<b>{cat}</b>  <font color='{hex_col}'>{score}/10 — {_score_label(score)}</font>",
            styles["ISubHead"],
        ))
        cat_findings = findings_all.get(cat, [])
        if cat_findings:
            for f in cat_findings:
                story.append(Paragraph(f"• {f}", styles["IBullet"]))
        else:
            story.append(Paragraph("• No detailed findings recorded.", styles["IBullet"]))
        story.append(Spacer(1, 4))

    # --- KEY FACTS ---
    story.append(Paragraph("Key Facts for the Conversation", styles["IHead"]))

    bs_type = agg.get("booking_system_type", "unknown")
    bs_name = agg.get("booking_platform_name")
    bs_label = f"{bs_type} ({bs_name})" if bs_name else bs_type
    ins_spec = agg.get("insurance_specificity", "none")
    providers = agg.get("insurance_providers_found", [])
    svc_p = agg.get("service_presentation", {})

    facts = [
        ("Booking system",       bs_label),
        ("Insurance info",       f"{ins_spec}" + (f" — providers: {', '.join(providers)}" if providers else "")),
        ("Direct billing",       "Yes" if agg.get("direct_billing_mentioned") else "No"),
        ("Testimonials on site", "Yes" if (agg.get("has_testimonial_content") or agg.get("has_review_widget")) else "None"),
        ("Star ratings shown",   "Yes" if agg.get("has_star_rating") else "No"),
        ("GBP link",             "Yes" if agg.get("has_gbp_link") else "No"),
        ("Google Map on contact","Yes" if agg.get("google_map_on_contact") else "No"),
        ("LocalBusiness schema", "Yes" if agg.get("has_local_schema") else "No"),
        ("Services page",        f"Yes — {svc_p.get('services_page_url','')}" if svc_p.get("has_services_page") else "No"),
        ("Service descriptions", "Yes" if svc_p.get("services_have_descriptions") else "No"),
        ("Clickable phone",      "Yes" if agg.get("has_clickable_phone") else "No"),
        ("Hours displayed",      "Yes" if agg.get("has_hours") else "No"),
        ("Pages analyzed",       str(len(data.get("pages_analyzed", [])))),
    ]

    fact_rows = [[f"{k}:", v] for k, v in facts]
    ft = Table(fact_rows, colWidths=[1.8*inch, 5.0*inch])
    ft.setStyle(TableStyle([
        ("FONTNAME",  (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",  (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE",  (0, 0), (-1, -1), 9),
        ("VALIGN",    (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",(0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",(0,0),(-1,-1), 3),
        ("TEXTCOLOR", (0, 0), (0, -1), DARK),
        ("TEXTCOLOR", (1, 0), (1, -1), MID),
    ]))
    story.append(ft)

    # --- SUGGESTED SERVICES TO PITCH ---
    story.append(Paragraph("Suggested Services to Offer", styles["IHead"]))

    SUGGESTIONS = {
        "Trust / Reviews": (
            "Add patient reviews — Embed Google reviews widget on homepage, add a "
            "testimonial section with real patient quotes, link to Google Business Profile."
        ),
        "Booking Conversion": (
            "Online booking setup — Replace contact form with Janeapp, Cliniko, or similar "
            "real-time booking system. Add prominent 'Book Now' CTA on homepage."
            if bs_type == "form" else
            "Improve booking visibility — Add dedicated /book page, make booking CTA "
            "visible above the fold on homepage."
        ),
        "Services Visibility": (
            "Services page redesign — Build a proper services page with descriptions for each "
            "service and dedicated sub-pages for major offerings."
        ),
        "Insurance / Accessibility": (
            "Insurance clarity page — List specific providers, explain direct billing process "
            "clearly, add to homepage or prominent navigation link."
        ),
        "Local Relevance": (
            "Local SEO improvements — Add Google Map embed on contact page, implement "
            "LocalBusiness JSON-LD schema, add neighbourhood targeting to content."
        ),
        "Contact Completeness": (
            "Contact page audit — Ensure phone number has a tel: link (mobile-friendly), "
            "hours of operation are visible, contact info is in the header/footer."
        ),
    }

    weak = [(cat, score) for cat, score in scores_dict.items() if score <= 6]
    weak.sort(key=lambda x: x[1])
    if weak:
        for cat, score in weak:
            suggestion = SUGGESTIONS.get(cat)
            if suggestion:
                story.append(Paragraph(f"<b>{cat} ({score}/10):</b>", styles["ISubHead"]))
                story.append(Paragraph(suggestion, styles["IBullet"]))
                story.append(Spacer(1, 3))
    else:
        story.append(Paragraph("No weak categories — site is performing well across all areas.", styles["IBody"]))

    # --- FOOTER ---
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#cccccc")))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"Generated by auditv.py · {datetime.now().strftime('%Y-%m-%d %H:%M')} · "
        f"{len(data.get('pages_analyzed', []))} pages analyzed · INTERNAL USE ONLY",
        styles["IFoot"],
    ))

    doc.build(story)
    print(f"  PDF saved to:  {pdf_path}")


# ===========================================================================
# MAIN ENTRY POINT
# ===========================================================================

def main():
    print("\n" + "=" * 56)
    print("  CLINIC WEBSITE AUDIT TOOL — v1")
    print("=" * 56)

    # Get optional PageSpeed API key from environment
    pagespeed_api_key = os.environ.get("GOOGLE_PAGESPEED_API_KEY")

    # --- Input ---
    raw_url = input("\nEnter clinic website URL: ").strip()
    if not raw_url:
        print("No URL provided. Exiting.")
        sys.exit(1)

    # Ensure scheme is present
    if not raw_url.startswith(("http://", "https://")):
        raw_url = "https://" + raw_url

    homepage_url = normalize_url(raw_url)
    base_domain = urlparse(homepage_url).netloc.lstrip("www.")

    print(f"\nAuditing: {homepage_url}")
    if not pagespeed_api_key:
        print("(PageSpeed API disabled — set GOOGLE_PAGESPEED_API_KEY to enable mobile performance testing)")
    print("Fetching homepage...", end=" ", flush=True)

    # --- Fetch homepage ---
    homepage_html = fetch_page(homepage_url)
    if not homepage_html:
        print(f"\nFailed to fetch homepage: {homepage_url}")
        print("Check the URL and try again.")
        sys.exit(1)
    print("OK")

    # --- Detect business name ---
    business_name = detect_business_name(homepage_html, base_domain)
    print(f"Business detected: {business_name}")

    # --- Collect candidate pages ---
    print("Collecting candidate pages...", end=" ", flush=True)
    candidates = collect_candidate_pages(homepage_url, homepage_html, base_domain)
    print(f"{len(candidates)} candidates")

    # Show which pages will be crawled (for debugging/transparency)
    print("\n  Pages to analyze:")
    for i, url in enumerate(candidates, 1):
        print(f"    {i}. {url}")
    print()

    # --- Fetch and analyze each page (parallel fetch + parallel analyze) ---
    print("Analyzing pages...")
    page_signals = []
    analyzed_urls = []

    # Prepare list of pages to fetch (excluding homepage, which is already loaded)
    pages_to_fetch = []
    for page_url in candidates:
        is_homepage = normalize_url(page_url) == normalize_url(homepage_url)
        if not is_homepage:
            pages_to_fetch.append(page_url)

    # First, add homepage signals
    signals = extract_page_signals(homepage_url, homepage_html, pagespeed_api_key=pagespeed_api_key)
    page_signals.append(signals)
    analyzed_urls.append(homepage_url)

    # Fetch all pages in parallel (4 concurrent workers)
    fetched_pages = {}  # url -> html mapping
    if pages_to_fetch:
        import time
        with ThreadPoolExecutor(max_workers=2) as fetch_executor:  # Reduced from 4 to 2 to avoid rate limiting
            future_to_url = {}
            for idx, url in enumerate(pages_to_fetch):
                # Stagger the requests slightly to avoid rate limiting
                time.sleep(0.1 * idx)
                future_to_url[fetch_executor.submit(fetch_page, url)] = url

            # Collect all fetched pages
            for future in as_completed(future_to_url):
                page_url = future_to_url[future]
                try:
                    html = future.result()
                    if html:
                        fetched_pages[page_url] = html
                        print(f"  {page_url}... fetched", flush=True)
                    else:
                        print(f"  {page_url}... skipped (no response)", flush=True)
                except Exception as e:
                    print(f"  {page_url}... skipped (fetch error: {e})", flush=True)

    # Now analyze all fetched pages in parallel (4 concurrent workers)
    if fetched_pages:
        def analyze_page(url_html_tuple):
            url, html = url_html_tuple
            return url, extract_page_signals(url, html, pagespeed_api_key=pagespeed_api_key)

        with ThreadPoolExecutor(max_workers=4) as analyze_executor:
            futures = {
                analyze_executor.submit(analyze_page, (url, html)): url
                for url, html in fetched_pages.items()
            }

            # Collect analysis results
            for future in as_completed(futures):
                try:
                    url, signals = future.result()
                    page_signals.append(signals)
                    analyzed_urls.append(url)
                except Exception as e:
                    print(f"  Analysis error: {e}", flush=True)

    if not page_signals:
        print("No pages could be analyzed. Exiting.")
        sys.exit(1)

    # --- Aggregate ---
    agg = aggregate_signals(page_signals, homepage_url)

    # --- Score ---
    scores = score_site(agg)

    # --- Priority Issues ---
    issues = generate_priority_issues(scores)

    # --- Design & Accessibility Assessment ---
    design_assessment = assess_design_quality(agg, page_signals)

    # --- Print Report ---
    print_report(
        url=homepage_url,
        business_name=business_name,
        agg=agg,
        scores=scores,
        issues=issues,
        page_signals=page_signals,
        analyzed_urls=analyzed_urls,
    )

    # --- Save JSON ---
    json_path = save_json_report(
        url=homepage_url,
        business_name=business_name,
        agg=agg,
        scores=scores,
        issues=issues,
        page_signals=page_signals,
        analyzed_urls=analyzed_urls,
        design_assessment=design_assessment,
    )

    # --- Save internal PDF brief ---
    import json as _json
    pdf_path = json_path.replace(".json", ".pdf")
    with open(json_path, "r", encoding="utf-8") as _f:
        _audit_data = _json.load(_f)
    save_internal_pdf(_audit_data, pdf_path)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    main()
