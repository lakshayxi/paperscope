#!/usr/bin/env python3
"""
expl.py — OpenReview Skill Trainer CLI

Fetches real peer reviews from OpenReview, analyzes patterns via Claude,
and writes a venue-calibrated reviewer skill (SKILL.md + reference files).

Usage:
    pip install openreview-py anthropic requests
    export ANTHROPIC_API_KEY=sk-...
    export OPENREVIEW_USERNAME=your_username
    export OPENREVIEW_PASSWORD=your_password

    python expl.py forum --url 
    python expl.py bulk --venues iclr neurips --years 2024 2025
    python expl.py analyze --group iclr neurips
    python expl.py skill
    python expl.py all
"""

import os, json, time, re, sys, argparse, random, itertools
from pathlib import Path
from urllib.parse import urlparse, parse_qs

try:
    import openreview
except ImportError:
    sys.exit("Missing dependency: pip install openreview-py")

try:
    import anthropic
except ImportError:
    sys.exit("Missing dependency: pip install anthropic")

try:
    import requests as _requests
except ImportError:
    _requests = None  # web fallback disabled

# ── Config ────────────────────────────────────────────────────────────────────

REVIEWS_PER_VENUE = 80
OUTPUT_DIR        = Path("skill")
CORPUS_FILE       = Path("corpus.json")
ANALYSIS_FILE     = Path("analysis_results.json")
CLAUDE_MODEL      = "claude-opus-4-5"

# ── Venue registry ────────────────────────────────────────────────────────────
# (display_name, venue_id, api_version, family)
# family is used for --venues filtering (lowercase)
# api_version: "v1" = api.openreview.net, "v2" = api2.openreview.net

VENUES = [
    # ── ML / Theory ───────────────────────────────────────────────────────────
    ("ICLR 2026",    "ICLR.cc/2026/Conference",              "v2", "iclr"),
    ("ICLR 2025",    "ICLR.cc/2025/Conference",              "v2", "iclr"),
    ("ICLR 2024",    "ICLR.cc/2024/Conference",              "v2", "iclr"),
    ("ICLR 2023",    "ICLR.cc/2023/Conference",              "v2", "iclr"),

    ("NeurIPS 2025", "NeurIPS.cc/2025/Conference",           "v2", "neurips"),
    ("NeurIPS 2024", "NeurIPS.cc/2024/Conference",           "v2", "neurips"),
    ("NeurIPS 2023", "NeurIPS.cc/2023/Conference",           "v2", "neurips"),

    ("ICML 2025",    "ICML.cc/2025/Conference",              "v2", "icml"),
    ("ICML 2024",    "ICML.cc/2024/Conference",              "v2", "icml"),
    ("ICML 2023",    "ICML.cc/2023/Conference",              "v1", "icml"),
    ("TMLR",         "TMLR",                                  "v1", "icml"),

    # ── NLP ───────────────────────────────────────────────────────────────────
    ("ACL 2025",     "aclweb.org/ACL/2025/Conference",       "v2", "acl"),
    ("ACL 2024",     "aclweb.org/ACL/2024/Conference",       "v2", "acl"),
    ("ACL 2023",     "aclweb.org/ACL/2023/Conference",       "v2", "acl"),

    ("EMNLP 2025",   "EMNLP/2025/Conference",                "v2", "acl"),
    ("EMNLP 2024",   "EMNLP/2024/Conference",                "v2", "acl"),
    ("EMNLP 2023",   "EMNLP/2023/Conference",                "v2", "acl"),

    ("NAACL 2025",   "NAACL/2025/Conference",                "v2", "acl"),
    ("NAACL 2024",   "NAACL/2024/Conference",                "v2", "acl"),

    ("CoLM 2024",    "colmweb.org/COLM/2024/Conference",     "v2", "acl"),

    # ── Vision ────────────────────────────────────────────────────────────────
    ("CVPR 2025",    "thecvf.com/CVPR/2025/Conference",      "v2", "cvpr"),
    ("CVPR 2024",    "thecvf.com/CVPR/2024/Conference",      "v2", "cvpr"),
    ("CVPR 2023",    "thecvf.com/CVPR/2023/Conference",      "v2", "cvpr"),
    ("ICCV 2023",    "thecvf.com/ICCV/2023/Conference",      "v2", "cvpr"),
    ("ECCV 2024",    "thecvf.com/ECCV/2024/Conference",      "v2", "cvpr"),

    # ── AI General ────────────────────────────────────────────────────────────
    ("AAAI 2026",    "AAAI.org/2026/Conference",              "v2", "aaai"),
    ("AAAI 2025",    "AAAI.org/2025/Conference",              "v2", "aaai"),
    ("AAAI 2024",    "AAAI.org/2024/Conference",              "v2", "aaai"),
    ("AAAI 2023",    "AAAI.org/2023/Conference",              "v2", "aaai"),

    ("IJCAI 2024",   "ijcai.org/2024/Conference",             "v2", "aaai"),
    ("IJCAI 2023",   "ijcai.org/2023/Conference",             "v2", "aaai"),

    # ── Data Mining ───────────────────────────────────────────────────────────
    ("KDD 2024",     "KDD.org/2024/Conference",               "v2", "kdd"),
    ("KDD 2023",     "KDD.org/2023/Conference",               "v2", "kdd"),
]

VENUE_GROUPS = {
    "iclr":    ["ICLR 2023", "ICLR 2024", "ICLR 2025", "ICLR 2026"],
    "neurips": ["NeurIPS 2023", "NeurIPS 2024", "NeurIPS 2025"],
    "icml":    ["ICML 2023", "ICML 2024", "ICML 2025", "TMLR"],
    "acl":     ["ACL 2023", "ACL 2024", "ACL 2025",
                "EMNLP 2023", "EMNLP 2024", "EMNLP 2025",
                "NAACL 2024", "NAACL 2025", "CoLM 2024"],
    "cvpr":    ["CVPR 2023", "CVPR 2024", "CVPR 2025", "ICCV 2023", "ECCV 2024"],
    "aaai":    ["AAAI 2023", "AAAI 2024", "AAAI 2025", "AAAI 2026",
                "IJCAI 2023", "IJCAI 2024"],
    "kdd":     ["KDD 2023", "KDD 2024"],
}

# ── OpenReview client management ──────────────────────────────────────────────

_client_v1 = None
_client_v2 = None


def get_client(version: str):
    global _client_v1, _client_v2
    username = os.environ.get("OPENREVIEW_USERNAME", "")
    password = os.environ.get("OPENREVIEW_PASSWORD", "")
    if version == "v1":
        if _client_v1 is None:
            kwargs = dict(baseurl="https://api.openreview.net")
            if username and password:
                kwargs.update(username=username, password=password)
            _client_v1 = openreview.Client(**kwargs)
        return _client_v1
    else:
        if _client_v2 is None:
            kwargs = dict(baseurl="https://api2.openreview.net")
            if username and password:
                kwargs.update(username=username, password=password)
            _client_v2 = openreview.api.OpenReviewClient(**kwargs)
        return _client_v2


def discover_review_invitation(client, venue_id: str, version: str):
    """Dynamically discover the review invitation ID for a venue.

    Never uses hardcoded suffixes. Algorithm:
    1. Fast path: probe /-/Official_Review then /-/Review with limit=1.
    2. Slow path: list all invitations and regex-match for review pattern.
    3. Cross-version fallback: if v2 fails, retry with v1 client.

    Returns the invitation ID string, or None on total failure.
    """
    review_re = re.compile(r'/official[_-]?review$|/review$', re.I)

    def _probe(c, ver):
        for suffix in ("Official_Review", "Review"):
            inv = f"{venue_id}/-/{suffix}"
            try:
                if ver == "v2":
                    notes = list(itertools.islice(c.get_all_notes(invitation=inv), 1))
                else:
                    notes = c.get_notes(invitation=inv, limit=1)
                if notes:
                    return inv
            except Exception:
                pass
            try:
                c.get_invitation(inv)
                return inv
            except Exception as e:
                err = str(e)
                if "403" in err or "Forbidden" in err or "permission" in err.lower():
                    return inv  # invitation exists, metadata just restricted
        try:
            if ver == "v2":
                invs = c.get_all_invitations(domain=venue_id)
                if not invs:
                    invs = c.get_all_invitations(prefix=venue_id)
            else:
                invs = c.get_invitations(regex=re.escape(venue_id) + ".*")
            for inv in invs:
                if review_re.search(inv.id):
                    return inv.id
        except Exception:
            pass
        return None

    result = _probe(client, version)
    if result:
        return result

    other_ver = "v1" if version == "v2" else "v2"
    try:
        result = _probe(get_client(other_ver), other_ver)
    except Exception:
        result = None
    return result

# ── Note parsing ──────────────────────────────────────────────────────────────

def get_field(content: dict, key: str) -> str:
    """Extract a field from note content, handling {value: ...} dicts."""
    v = content.get(key, "")
    if isinstance(v, dict):
        return v.get("value", "")
    return str(v) if v else ""


def parse_review_note(note) -> dict:
    """Parse a review note into a structured dict."""
    c = note.content if isinstance(note.content, dict) else {}
    rating_raw = (get_field(c, "rating") or get_field(c, "recommendation")
                  or get_field(c, "score") or get_field(c, "overall") or "")
    m = re.search(r"[\d.]+", str(rating_raw))
    return {
        "note_id":    getattr(note, "id", None),
        "forum_id":   getattr(note, "forum", None),
        "rating":     rating_raw,
        "rating_num": float(m.group()) if m else None,
        "confidence": get_field(c, "confidence"),
        "summary":    get_field(c, "summary") or get_field(c, "title"),
        "text":       (get_field(c, "review") or get_field(c, "comment")
                       or get_field(c, "main_review")),
        "strengths":  get_field(c, "strengths"),
        "weaknesses": get_field(c, "weaknesses"),
        "questions":  get_field(c, "questions") or get_field(c, "limitations"),
    }


def parse_paper_note(note) -> dict:
    """Parse a paper/submission note into structured metadata."""
    c = note.content if isinstance(note.content, dict) else {}
    authors  = get_field(c, "authors")
    if isinstance(authors, list):
        authors = ", ".join(authors)
    keywords = get_field(c, "keywords")
    if isinstance(keywords, list):
        keywords = ", ".join(keywords)
    return {
        "forum_id": getattr(note, "id", None),
        "title":    get_field(c, "title"),
        "abstract": get_field(c, "abstract"),
        "keywords": keywords,
        "authors":  authors,
        "venue":    get_field(c, "venue") or get_field(c, "venueid"),
    }

# ── Forum fetch — web scraping fallback (no credentials needed) ───────────────

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _web_field(content: dict, *keys) -> str:
    for key in keys:
        v = content.get(key, "")
        if isinstance(v, dict):
            v = v.get("value", "")
        if isinstance(v, list) and v:
            v = v[0] if isinstance(v[0], str) else str(v[0])
        if v:
            return str(v)
    return ""


def _classify_inv(inv) -> str:
    if isinstance(inv, list):
        inv = inv[0] if inv else ""
    inv = str(inv)
    if re.search(r'/official[_-]?review$|/review$', inv, re.I):
        return "review"
    if re.search(r'/author|/rebuttal|/official_comment', inv, re.I):
        return "rebuttal"
    if re.search(r'/meta_review$|/decision$', inv, re.I):
        return "decision"
    return "other"


def fetch_forum_web(forum_id: str) -> dict:
    """Scrape a forum from openreview.net without credentials.

    OpenReview uses Next.js — forum data is embedded in __NEXT_DATA__.
    This is the same data a browser (or ChatGPT) reads from the URL.
    """
    if _requests is None:
        raise RuntimeError("pip install requests  to enable web fallback")

    url = f"https://openreview.net/forum?id={forum_id}"
    print(f"  [web] fetching {url}", flush=True)
    resp = _requests.get(url, headers=_BROWSER_HEADERS, timeout=20)
    if resp.status_code == 403:
        raise RuntimeError(
            "openreview.net returned 403 even with browser User-Agent.\n"
            "Set OPENREVIEW_USERNAME / OPENREVIEW_PASSWORD for API access."
        )
    resp.raise_for_status()

    m = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        resp.text, re.DOTALL
    )
    if not m:
        raise RuntimeError("No __NEXT_DATA__ found — OpenReview may have changed their frontend.")

    page_props = json.loads(m.group(1)).get("props", {}).get("pageProps", {})

    paper_dict = page_props.get("forumNote") or page_props.get("note") or {}
    all_notes  = page_props.get("notes") or page_props.get("replyNotes") or []

    pc = paper_dict.get("content", {})
    paper = {
        "forum_id": forum_id,
        "title":    _web_field(pc, "title"),
        "abstract": _web_field(pc, "abstract"),
        "keywords": _web_field(pc, "keywords"),
        "authors":  _web_field(pc, "authors"),
        "venue":    _web_field(pc, "venue", "venueid"),
    }

    reviews, rebuttals, decision, meta_rev = [], [], None, None

    for nd in all_notes:
        inv  = nd.get("invitation", "") or ""
        kind = _classify_inv(inv)
        c    = nd.get("content", {})
        if kind == "review":
            rating_raw = _web_field(c, "rating", "recommendation", "score", "overall")
            mn = re.search(r"[\d.]+", str(rating_raw))
            reviews.append({
                "note_id":    nd.get("id"),
                "forum_id":   forum_id,
                "rating":     rating_raw,
                "rating_num": float(mn.group()) if mn else None,
                "confidence": _web_field(c, "confidence"),
                "summary":    _web_field(c, "summary", "title"),
                "text":       _web_field(c, "review", "comment", "main_review"),
                "strengths":  _web_field(c, "strengths"),
                "weaknesses": _web_field(c, "weaknesses"),
                "questions":  _web_field(c, "questions", "limitations"),
            })
        elif kind == "rebuttal":
            text = _web_field(c, "comment", "reply", "text")
            if text:
                rebuttals.append(text)
        elif kind == "decision":
            text = _web_field(c, "decision", "metareview", "comment", "text")
            if re.search(r'/decision$', str(inv), re.I):
                decision = text
            else:
                meta_rev = text

    if not paper.get("title") and not reviews:
        raise RuntimeError(
            f"Parsed empty result — pageProps keys: {list(page_props.keys())}\n"
            "OpenReview may load notes dynamically. "
            "Set OPENREVIEW_USERNAME / OPENREVIEW_PASSWORD for API access."
        )

    return {
        "forum_id": forum_id,
        "paper":    paper,
        "reviews":  reviews,
        "rebuttals": rebuttals[:5],
        "decision": decision or meta_rev,
        "_source":  "web",
    }

# ── Forum fetch — main entry point ────────────────────────────────────────────

def parse_forum_id(url_or_id: str) -> str:
    if url_or_id.startswith("http"):
        qs = parse_qs(urlparse(url_or_id).query)
        return qs.get("id", [url_or_id])[0]
    return url_or_id


def fetch_forum(forum_id: str) -> dict:
    """Fetch a single forum. Tries API (v2 → v1), then web scraping on 403."""
    paper_note   = None
    used_version = None
    last_errors  = {}

    for ver in ("v2", "v1"):
        try:
            c = get_client(ver)
            paper_note = c.get_note(forum_id)
            used_version = ver
            break
        except Exception as e:
            last_errors[ver] = str(e)

    if paper_note is not None:
        client      = get_client(used_version)
        child_notes = client.get_notes(forum=forum_id)
        reviews, rebuttals, decision, meta_rev = [], [], None, None

        for note in child_notes:
            inv  = getattr(note, "invitation", "") or getattr(note, "invitations", "") or ""
            kind = _classify_inv(inv)
            if kind == "review":
                reviews.append(parse_review_note(note))
            elif kind == "rebuttal":
                cn   = note.content if isinstance(note.content, dict) else {}
                text = get_field(cn, "comment") or get_field(cn, "reply") or get_field(cn, "text")
                if text:
                    rebuttals.append(text)
            elif kind == "decision":
                cn   = note.content if isinstance(note.content, dict) else {}
                text = (get_field(cn, "decision") or get_field(cn, "metareview")
                        or get_field(cn, "comment") or get_field(cn, "text"))
                if re.search(r'/decision$', str(inv), re.I):
                    decision = text
                else:
                    meta_rev = text

        return {
            "forum_id": forum_id,
            "paper":    parse_paper_note(paper_note),
            "reviews":  reviews,
            "rebuttals": rebuttals[:5],
            "decision": decision or meta_rev,
            "_source":  used_version,
        }

    # API failed — try web fallback if 403
    forbidden = any("forbidden" in e.lower() or "403" in e.lower()
                    for e in last_errors.values())
    if forbidden:
        print("  [forum] API requires credentials (403). Trying web fallback...", flush=True)
        try:
            return fetch_forum_web(forum_id)
        except Exception as web_err:
            errors_str = "; ".join(f"{v}: {e}" for v, e in last_errors.items())
            raise RuntimeError(
                f"Forum '{forum_id}': API (403) and web scrape both failed.\n"
                f"API: {errors_str}\nWeb: {web_err}\n\n"
                "Fix: set OPENREVIEW_USERNAME / OPENREVIEW_PASSWORD."
            )

    errors_str = "; ".join(f"{v}: {e}" for v, e in last_errors.items())
    raise RuntimeError(
        f"Forum '{forum_id}' not found on either API version. "
        f"Check the ID or URL.\nErrors: {errors_str}"
    )

# ── Bulk fetch ────────────────────────────────────────────────────────────────

def _fetch_notes(client, venue_id: str, inv: str, version: str, n: int) -> list:
    """Fetch up to n review notes. For v2, uses submission-based sampling when
    the global invitation stream is empty (common for restricted invitations)."""
    if version != "v2":
        offset = random.randint(0, 200)
        notes = client.get_notes(invitation=inv, limit=n, offset=offset)
        if not notes and offset > 0:
            notes = client.get_notes(invitation=inv, limit=n, offset=0)
        return notes

    # v2: try global invitation stream first
    notes = list(itertools.islice(client.get_all_notes(invitation=inv), n))
    if notes:
        return notes

    # v2 fallback: sample submissions, collect their review child-notes
    print(f"    [fetch] invitation stream empty — sampling via submissions...", flush=True)
    subs = []
    for sub_suffix in ("Blind_Submission", "Submission", "Camera_Ready_Revision", "Research"):
        sub_inv = f"{venue_id}/-/{sub_suffix}"
        try:
            subs = list(itertools.islice(client.get_all_notes(invitation=sub_inv), 500))
            if subs:
                print(f"    [fetch] found {len(subs)} submissions via {sub_inv}", flush=True)
                break
        except Exception:
            pass

    if not subs:
        return []

    seen_file = Path(f".seen_{re.sub(r'[^a-z0-9]', '_', venue_id.lower())}.json")
    seen_ids  = set(json.loads(seen_file.read_text()) if seen_file.exists() else [])

    unseen = [s for s in subs if s.id not in seen_ids]
    random.shuffle(unseen)

    collected = []
    review_re = re.compile(r'/official[_-]?review$|/review$', re.I)
    for sub in unseen:
        if len(collected) >= n:
            break
        try:
            children = client.get_notes(forum=sub.id)
            for note in children:
                invitations = getattr(note, "invitations", []) or [getattr(note, "invitation", "")]
                if any(review_re.search(str(inv)) for inv in invitations):
                    collected.append(note)
            if children:
                seen_ids.add(sub.id)
        except Exception:
            pass

    seen_file.write_text(json.dumps(list(seen_ids)))
    print(f"    [fetch] {len(seen_ids)} forums seen so far ({len(unseen)} unseen available)", flush=True)
    return collected


def fetch_venue(name: str, venue_id: str, version: str, n: int = REVIEWS_PER_VENUE) -> list:
    """Fetch up to n reviews for a single venue-year. Never raises."""
    print(f"  [{name}] connecting...", flush=True)
    try:
        client = get_client(version)
        inv = discover_review_invitation(client, venue_id, version)
        if not inv:
            print(f"  [{name}] ✗ no review invitation found", flush=True)
            return []

        notes = _fetch_notes(client, venue_id, inv, version, n)

        parsed = [parse_review_note(note) for note in notes]
        parsed = [r for r in parsed if len(r.get("text", "") + r.get("strengths", "") + r.get("weaknesses", "")) > 50]
        print(f"  [{name}] ✓ {len(parsed)} reviews via {inv}", flush=True)
        time.sleep(2)
        return parsed

    except Exception as e:
        err = str(e)
        if "429" in err or "Too many requests" in err:
            wait = 65
            print(f"  [{name}] rate-limited — waiting {wait}s...", flush=True)
            time.sleep(wait)
        else:
            print(f"  [{name}] ✗ {e}", flush=True)
        return []


def corpus_path_for(venues_filter) -> Path:
    """Return corpus_<family>.json for a single-family filter, else corpus.json."""
    if venues_filter and len(venues_filter) == 1:
        return Path(f"corpus_{venues_filter[0]}.json")
    return CORPUS_FILE


def build_corpus(venues_filter, years_filter, per_venue: int, force: bool,
                 out_file: Path = None) -> dict:
    """Fetch reviews for all (or filtered) venues, save incrementally."""
    if out_file is None:
        out_file = corpus_path_for(venues_filter)

    corpus = {}
    if out_file.exists() and not force:
        corpus = json.loads(out_file.read_text())
        total = sum(len(v) for v in corpus.values() if isinstance(v, list))
        print(f"Loaded existing corpus ({total} reviews across {len(corpus)} entries) from {out_file}")

    for name, venue_id, version, family in VENUES:
        if venues_filter and family not in venues_filter:
            continue
        if years_filter and name != "TMLR":
            ym = re.search(r'\d{4}', name)
            if not ym or int(ym.group()) not in years_filter:
                continue
        reviews = fetch_venue(name, venue_id, version, per_venue)
        if not reviews:
            continue
        existing = corpus.get(name, []) if not force else []
        seen_ids = {r["note_id"] for r in existing if r.get("note_id")}
        new = [r for r in reviews if r.get("note_id") not in seen_ids]
        if not new:
            print(f"  [{name}] no new reviews found", flush=True)
            continue
        corpus[name] = existing + new
        print(f"  [{name}] +{len(new)} new reviews (total: {len(corpus[name])})", flush=True)
        out_file.write_text(json.dumps(corpus, indent=2))

        # write inbox — only the new batch for Claude to read
        inbox_file = out_file.with_stem(out_file.stem + "_inbox")
        inbox = json.loads(inbox_file.read_text()) if inbox_file.exists() else {}
        inbox[name] = inbox.get(name, []) + new
        inbox_file.write_text(json.dumps(inbox, indent=2))

    return corpus


def compress_corpus(corpus: dict) -> dict:
    """Strip corpus down to fields needed for skill analysis — reduces file size ~70%."""
    keep = ("rating", "rating_num", "confidence", "summary", "text", "strengths", "weaknesses", "questions")
    out = {}
    for venue, reviews in corpus.items():
        if not isinstance(reviews, list):
            out[venue] = reviews
            continue
        out[venue] = [
            {k: (str(r[k])[:400] if isinstance(r.get(k), str) else r.get(k))
             for k in keep if r.get(k)}
            for r in reviews
        ]
    return out

# ── Analysis ──────────────────────────────────────────────────────────────────

def format_sample(reviews: list, n: int = 35) -> str:
    lines = []
    for i, r in enumerate(reviews[:n]):
        score = f"score={r['rating']}" if r.get("rating") else ""
        conf  = f"conf={r['confidence']}" if r.get("confidence") else ""
        meta  = " ".join(filter(None, [score, conf]))
        lines.append(f"[R{i+1} {meta}]")
        if r.get("strengths"):  lines.append(f"Strengths: {str(r['strengths'])[:200]}")
        if r.get("weaknesses"): lines.append(f"Weaknesses: {str(r['weaknesses'])[:200]}")
        if r.get("text"):       lines.append(str(r["text"])[:300])
        lines.append("---")
    return "\n".join(lines)[:5000]


def build_analysis_prompt(group_name: str, reviews: list, year_labels: list) -> str:
    scores  = [r["rating_num"] for r in reviews if r.get("rating_num") is not None]
    avg     = sum(scores) / len(scores) if scores else None
    lo      = min(scores) if scores else None
    hi      = max(scores) if scores else None
    avg_str = f"{avg:.2f}" if avg is not None else "N/A"
    accept  = [s for s in scores if s >= (hi * 0.65 if hi else 5)]
    reject  = [s for s in scores if s < (hi * 0.65 if hi else 5)]

    return f"""Analyze these real peer reviews from {group_name} ({', '.join(year_labels)}).
Stats: {len(reviews)} reviews | score range {lo}–{hi} | avg {avg_str} | ~{len(accept)} accept-tier | ~{len(reject)} reject-tier

REVIEWS:
{format_sample(reviews)}

Write a venue calibration reference file in Markdown. Include exactly these 7 sections, numbered:

## 1. Score Calibration
Table: score → label → real-world acceptance meaning (based on actual distribution above).
Include the borderline threshold, clear-accept threshold, and clear-reject threshold.

## 2. Top 5 Accept Signals
Patterns that correlate with high scores at this venue.
Quote real reviewer language in "quotes" for each signal.

## 3. Top 5 Reject Signals
Patterns that correlate with low scores at this venue.
Quote real reviewer language in "quotes" for each signal.

## 4. Hidden Criteria
2–3 bullets: unwritten rules this venue enforces not stated in their CFP, inferred from the review data.

## 5. Reviewer Language Patterns
Two lists of 5 exact phrases or sentence openings:
- Accept-tier reviewers use:
- Reject-tier reviewers use:

## 6. Year-over-Year Drift
1–3 bullets: how standards or emphasis shifted across {', '.join(year_labels)} based on the data.
(Write "Insufficient data for trend analysis" if fewer than 2 years represented.)

## 7. Rebuttal Effectiveness
Based on the question patterns and any follow-up language in the reviews:
- What kinds of author responses tend to raise scores?
- What rebuttals typically have no effect?
- What issues are "fatal flaws" no rebuttal can fix?

Source: {len(reviews)} reviews from OpenReview ({', '.join(year_labels)})
Be concrete. Quote real reviewer language. No generic advice. This calibrates actual reviewer scores."""


def analyze_group(claude_client, group_name: str, reviews: list, year_labels: list) -> str:
    prompt  = build_analysis_prompt(group_name, reviews, year_labels)
    message = claude_client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def analyze_all(corpus: dict, groups_filter) -> dict:
    """Run analyze_group for each venue group. Saves results incrementally."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        sys.exit("Set ANTHROPIC_API_KEY environment variable before running analyze.")

    claude  = anthropic.Anthropic(api_key=api_key)
    results = {}
    if ANALYSIS_FILE.exists():
        results = json.loads(ANALYSIS_FILE.read_text())

    for group_name, venue_names in VENUE_GROUPS.items():
        if groups_filter and group_name not in groups_filter:
            continue
        if group_name in results:
            print(f"  [{group_name}] skipped (already analyzed)")
            continue

        group_reviews, found_years = [], []
        for vn in venue_names:
            revs = corpus.get(vn, [])
            if isinstance(revs, list) and revs:
                group_reviews.extend(revs)
                found_years.append(vn)

        if not group_reviews:
            print(f"  [{group_name}] skipped — no data in corpus")
            continue

        print(f"  [{group_name}] analyzing {len(group_reviews)} reviews "
              f"({', '.join(found_years)})...", flush=True)
        try:
            text = analyze_group(claude, group_name, group_reviews, found_years)
            results[group_name] = text
            ANALYSIS_FILE.write_text(json.dumps(results, indent=2))
            print(f"  [{group_name}] ✓ done")
        except Exception as e:
            print(f"  [{group_name}] ✗ {e}")
        time.sleep(1)

    return results

# ── Skill generation ──────────────────────────────────────────────────────────

SKILL_MD_TEMPLATE = '''\
---
name: openreview-reviewer
description: >
  A venue-calibrated ML paper reviewer trained on real OpenReview data (2023–2026).
  Use whenever the user wants to review, critique, evaluate, or grade an AI/ML/DS
  research paper — especially when they mention a target venue (ICLR, NeurIPS, ICML,
  ACL, EMNLP, CVPR, ICCV, ECCV, AAAI, KDD, etc.). Also trigger for: "review this
  paper", "what score would this get", "is this good enough for X", "write a reviewer
  report", "pretend you are a reviewer", or when the user pastes an abstract or PDF
  link. This skill encodes real reviewer patterns from OpenReview — not generic advice.
  Load the venue reference from references/ before writing any review.
---

# OpenReview-Calibrated Reviewer (2023–2026)

You are a senior ML researcher with area-chair-level experience. Your reviews match
the **actual distribution of accepted/rejected papers at each venue**, calibrated on
real OpenReview data.

---

## Step 0 — Venue Detection → Load Reference

Identify the target venue first. Then load the corresponding reference file before
writing anything.

{groups_table}

TMLR data is included in `references/icml.md`.

**Do not write a single line of review before loading the venue reference.**

---

## Step 1 — Input Tier

| Tier | Input | Caveats |
|---|---|---|
| T0 | Idea / concept only | All sections limited — state this clearly |
| T1 | Abstract only | Novelty and contribution sections limited |
| T2 | Partial paper | Note exactly what sections are missing |
| T3 | Full paper | Full review, no caveats |

---

## Step 2 — Paper Type

Detect and state. The entire review lens shifts:

- **Empirical** → experimental design, baselines, statistical validity are primary
- **Theoretical** → proof correctness, assumption strength, bound tightness
- **Systems** → throughput, latency, engineering novelty, deployment
- **Survey/Position** → coverage, taxonomy quality, citation fairness
- **Hybrid** → apply both relevant lenses, note any conflicts

---

## The Review

### §1 Contribution Audit
Your words, not the abstract\'s. One sentence. Then:
- Is the claim proportional to the evidence?
- What is the actual delta over prior work?
- Is the problem formulation artificially narrow to appear novel?

### §2 Novelty
- Name 2–3 closest prior works. Flag uncertainty.
- Where is the novelty: formulation / architecture / training / evaluation?
- Incremental rebranding vs genuine contribution?

### §3 Technical Validity
Per major component: what it does → why chosen → correctness → hidden assumptions.

### §4 Experimental Assessment
- Baselines: SOTA, last 12 months?
- Dataset breadth: single dataset is a weakness at top venues
- Statistical validity: seeds, error bars, significance tests
- Reproducibility: code, hyperparameters, compute budget

### §5 Strengths
Numbered list, ranked by weight. Technical only — no filler ("writing is clear").

### §6 Weaknesses
Ranked by severity. Template: "[Component] is weak because [specific evidence],
which means [consequence]."

### §7 Questions for Authors
2–5, ordered by importance. Flag which answers would raise your score.

### §8 Hidden Issues Checklist

| Issue | Check |
|---|---|
| Data leakage | Preprocessing before split? Val-as-test? |
| Unfair baselines | Different compute/data? Suboptimal baseline hyperparams? |
| Missing obvious baseline | What simplest thing was omitted? |
| Metric gaming | Does the metric best favor this method? |
| Cherry-picking | Only best dataset/seed/split reported? |
| Reproducibility gap | Can you rerun from paper alone? |

### §9 Score
**Use the venue-calibrated scoring from the loaded reference file — not a generic scale.**

```
Score:          [X] / [venue scale]
Confidence:     [venue scale]
Recommendation: [venue-specific label]
Justification:  2–3 sentences linking evidence to score.
```

### §10 Rebuttal Prediction
- Is there a fatal flaw no rebuttal can fix?
- What author response would raise your score?
- If borderline: what would tip it either direction?
- (If a `_forum_*` entry exists in corpus for this paper, check rebuttal text for context.)

### §11 Learning Notes *(personal — not part of a real review)*
- Steal-worthy ideas for your own work
- Implementation difficulty: Easy / Medium / Hard / Very Hard
- Prerequisites to fully understand this paper
- Worth reading in depth? Yes / Skim / Skip

---

## Rules
- No filler. Every claim references specific evidence.
- Flag your own uncertainty explicitly.
- Never fabricate citations, scores, or numbers.
- T0/T1/T2: mark limited sections with ⚠️

---

## Keeping This Skill Current
Re-run `python expl.py all` after each major conference cycle to update references.
'''


def write_skill(analysis_results: dict, output_dir: Path) -> None:
    refs_dir = output_dir / "references"
    refs_dir.mkdir(parents=True, exist_ok=True)

    table_rows = ["| Venue family | Reference file |", "|---|---|"]
    venue_labels = {
        "iclr":    "ICLR",
        "neurips": "NeurIPS",
        "icml":    "ICML / TMLR",
        "acl":     "ACL / EMNLP / NAACL / CoLM",
        "cvpr":    "CVPR / ICCV / ECCV",
        "aaai":    "AAAI / IJCAI",
        "kdd":     "KDD",
    }
    for group in analysis_results:
        label = venue_labels.get(group, group.upper())
        table_rows.append(f"| {label} | `references/{group}.md` |")

    skill_text = SKILL_MD_TEMPLATE.format(groups_table="\n".join(table_rows))
    (output_dir / "SKILL.md").write_text(skill_text)
    print(f"  Wrote {output_dir}/SKILL.md")

    for group, text in analysis_results.items():
        header = (f"# {group.upper()} Review Calibration\n"
                  f"*Auto-generated from real OpenReview data via expl.py*\n\n")
        path = refs_dir / f"{group}.md"
        path.write_text(header + text)
        print(f"  Wrote {path}")

# ── CLI command handlers ───────────────────────────────────────────────────────

def cmd_forum(args) -> None:
    forum_id = parse_forum_id(args.url)
    print(f"Fetching forum: {forum_id}", flush=True)
    result = fetch_forum(forum_id)
    print(json.dumps(result, indent=2))
    if args.save:
        corpus = {}
        if CORPUS_FILE.exists():
            corpus = json.loads(CORPUS_FILE.read_text())
        key = f"_forum_{forum_id}"
        corpus[key] = result
        CORPUS_FILE.write_text(json.dumps(corpus, indent=2))
        print(f"\nSaved to {CORPUS_FILE} under key '{key}'", flush=True)


def cmd_bulk(args) -> None:
    venues_filter = [v.lower() for v in args.venues] if args.venues else None
    years_filter  = [int(y) for y in args.years]     if args.years  else None
    out_file      = Path(args.output) if args.output else corpus_path_for(venues_filter)

    print("=" * 60)
    print("Fetching reviews from OpenReview")
    print("=" * 60)
    if venues_filter: print(f"  Venues: {', '.join(venues_filter)}")
    if years_filter:  print(f"  Years:  {', '.join(str(y) for y in years_filter)}")
    print(f"  Per venue: {args.per_venue}")
    print(f"  Output: {out_file}")

    corpus = build_corpus(venues_filter, years_filter, args.per_venue, args.force, out_file)
    bulk   = {k: v for k, v in corpus.items() if not k.startswith("_forum_")}
    total  = sum(len(v) for v in bulk.values() if isinstance(v, list))
    print(f"\nCorpus: {total} reviews across {len(bulk)} venue-years → {out_file}")

    if args.compress:
        compressed     = compress_corpus(bulk)
        compress_file  = out_file.with_stem(out_file.stem + "_compressed")
        compress_file.write_text(json.dumps(compressed, indent=2))
        orig_kb        = out_file.stat().st_size // 1024
        comp_kb        = compress_file.stat().st_size // 1024
        print(f"Compressed: {orig_kb}KB → {comp_kb}KB → {compress_file}")


def cmd_analyze(args) -> None:
    corpus_path = Path(args.corpus)
    if not corpus_path.exists():
        sys.exit(f"Corpus file not found: {corpus_path}. Run 'expl.py bulk' first.")
    corpus = json.loads(corpus_path.read_text())
    groups_filter = [g.lower() for g in args.group] if args.group else None

    print("=" * 60)
    print("Analyzing patterns with Claude")
    print("=" * 60)
    if groups_filter: print(f"  Groups: {', '.join(groups_filter)}")

    results = analyze_all(corpus, groups_filter)
    print(f"\nAnalyzed {len(results)} venue groups → {ANALYSIS_FILE}")


def cmd_skill(args) -> None:
    if not ANALYSIS_FILE.exists():
        sys.exit(f"Analysis file not found: {ANALYSIS_FILE}. Run 'expl.py analyze' first.")
    results = json.loads(ANALYSIS_FILE.read_text())
    if not results:
        sys.exit("No analysis results found. Run 'expl.py analyze' first.")

    output_dir = Path(args.output)
    print("=" * 60)
    print("Writing skill files")
    print("=" * 60)
    write_skill(results, output_dir)
    print(f"\nDone. Install the skill from '{output_dir}/'")
    print(f"  Rename {output_dir}/ → openreview-reviewer/ and zip as .skill to install.")


def cmd_all(args) -> None:
    print("=" * 60)
    print("OpenReview Skill Trainer — full pipeline")
    print("=" * 60)

    print("\n[1/3] Fetching reviews from OpenReview...")
    corpus = build_corpus(None, None, REVIEWS_PER_VENUE, force=False)
    bulk  = {k: v for k, v in corpus.items() if not k.startswith("_forum_")}
    total = sum(len(v) for v in bulk.values() if isinstance(v, list))
    print(f"\nCorpus: {total} reviews across {len(bulk)} venue-years → {CORPUS_FILE}")

    print("\n[2/3] Analyzing patterns with Claude...")
    results = analyze_all(corpus, None)
    print(f"Analyzed {len(results)} venue groups → {ANALYSIS_FILE}")

    print("\n[3/3] Writing skill files...")
    write_skill(results, OUTPUT_DIR)

    print("\n✓ Done. Install the skill from the 'skill/' directory.")
    print("  Rename skill/ → openreview-reviewer/ and zip as .skill to install.")

# ── CLI parser ────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="expl.py",
        description=(
            "OpenReview Skill Trainer — fetch real reviews, analyze with Claude, "
            "and write a venue-calibrated reviewer skill."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("forum", help="Fetch a single forum by URL or ID")
    p.add_argument("--url", required=True,
                   help="Forum URL (https://openreview.net/forum?id=XXX) or raw forum ID")
    p.add_argument("--save", action="store_true",
                   help=f"Save result to {CORPUS_FILE} under key _forum_<id>")
    p.set_defaults(func=cmd_forum)

    p = sub.add_parser("bulk",
                       help="Bulk-fetch reviews (requires OPENREVIEW_USERNAME + PASSWORD)")
    p.add_argument("--venues", nargs="+", metavar="FAMILY",
                   help="Families: iclr neurips icml acl cvpr aaai kdd. Default: all.")
    p.add_argument("--years", nargs="+", metavar="YEAR",
                   help="Years to include e.g. 2024 2025. Default: all.")
    p.add_argument("--per-venue", type=int, default=REVIEWS_PER_VENUE, metavar="N",
                   help=f"Reviews per venue-year (default: {REVIEWS_PER_VENUE})")
    p.add_argument("--force", action="store_true",
                   help="Re-fetch even if already cached")
    p.add_argument("--output", default=None, metavar="FILE",
                   help="Output file (default: corpus_<family>.json or corpus.json)")
    p.add_argument("--compress", action="store_true",
                   help="Also write a compressed version with only analysis-relevant fields")
    p.set_defaults(func=cmd_bulk)

    p = sub.add_parser("analyze", help="Analyze corpus with Claude → analysis_results.json")
    p.add_argument("--corpus", default=str(CORPUS_FILE), metavar="PATH",
                   help=f"Corpus file path (default: {CORPUS_FILE})")
    p.add_argument("--group", nargs="+", metavar="GROUP",
                   help="Groups to analyze: iclr neurips icml acl cvpr aaai kdd. Default: all.")
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser("skill", help="Write SKILL.md + reference files")
    p.add_argument("--output", default=str(OUTPUT_DIR), metavar="DIR",
                   help=f"Output directory (default: {OUTPUT_DIR})")
    p.set_defaults(func=cmd_skill)

    p = sub.add_parser("all", help="Full pipeline: bulk → analyze → skill")
    p.set_defaults(func=cmd_all)

    return parser


def main() -> None:
    build_parser().parse_args().__dict__["func"](build_parser().parse_args())


if __name__ == "__main__":
    main()
