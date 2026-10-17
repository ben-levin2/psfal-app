"""Checks on the dashboard data before it is shown, and the rules for retrying a data link that failed.

The data file is assembled by hand from the lab's saved reports, so its parts (the header week, the results, the remaining schedule, the
numbers to watch and the transfer statistics) can fall out of step. Nothing here changes or hides data: each check returns plain messages
that say what looks wrong and how to fix it, and the dashboard shows them as a warning.

Optional coverage metadata (older files without it still work):
    "meta": {"snapshot": "...", "through_week": 6,
             "coverage": {"watch": {"Offense success rate": {"through_week": 6, "games": 6}}, "transfers": 6}}
"transfers" is the week the transfer statistics were last computed through. "watch" is either one week for every number to watch, or, because
the numbers to watch need not cover the same games, a map from a card's label to its own coverage: the week it is through, the number of
completed games it includes, or both. A card with no stated coverage shows "Coverage not specified". The snapshot date and meta.through_week
describe the file as a whole and are never used as a metric's coverage.

Optional freshness metadata, read by section_freshness (older files without it still work):
    "meta": {"freshness": {"transfers": "NOT refreshed: through week 5 (...)"}, "last_successful_refresh": "2026-10-11T21:30:00-04:00"}
meta.freshness holds the builder's own note for a section; a note starting "NOT refreshed" marks that section stale. last_successful_refresh
is when the data file was last rebuilt successfully (ISO 8601). Neither is ever inferred: when the data do not state them, the dashboard says so.
"""
import re
import unicodedata
from datetime import date, datetime

from ui import game_date

# Every top-level field the dashboard reads, and the fields each game and each number to watch must have.
REQUIRED = ("meta", "games", "schedule", "watch", "seasons", "gap", "loses", "roster", "forecast", "traj", "ratingCorr", "calib", "watchClass",
            "transfers", "programs", "portalGroups", "yields", "openings", "weights", "modules")
GAME_FIELDS = ("wk", "opp", "res", "pf", "pa", "o", "d", "note")
WATCH_FIELDS = ("label", "now", "ref", "refLabel", "better")
META_FIELDS = ("snapshot", "through_week")
SECTIONS = {"watch": "Numbers to watch", "transfers": "Transfer statistics"}

RETRY_WAIT = 20  # seconds: after a data link fails, wait this long before any viewer's page tries it again

_WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen"]


def count_words(n, noun="game"):
    """5 -> 'five games', 1 -> 'one game'; numbers above fifteen are written as digits."""
    word = _WORDS[n] if 0 <= n < len(_WORDS) else str(n)
    return f"{word} {noun}{'' if n == 1 else 's'}"


def _week(g):
    w = g.get("wk") if isinstance(g, dict) else None
    return w if isinstance(w, int) and not isinstance(w, bool) else None


def latest_game(games):
    """The game with the highest week number, and None as the reason. The results carry week numbers but no dates, so the week decides;
    the order of the rows does not. When it is unclear (no game has a whole-number week, or two games share the highest week), returns
    (None, reason) so the dashboard can say so instead of picking one."""
    dated = [g for g in games if _week(g) is not None]
    if not dated:
        return None, ("no game in the results has a week number" if games else None)
    top = max(_week(g) for g in dated)
    at_top = [g for g in dated if _week(g) == top]
    if len(at_top) > 1:
        return None, f"{len(at_top)} games are listed for week {top}"
    return at_top[0], None


def results_weeks(games):
    """Whole-number weeks of the games in the results (for charts; rows without one are left out of week-based views)."""
    return [g for g in games if _week(g) is not None]


def _team(name):
    """'at Northwestern' / 'USC (White Out, 7:30 p.m.)' -> 'northwestern' / 'usc', for matching the results to the schedule. Text after the
    first comma or semicolon outside parentheses is a note, not part of the name ('USC (...), played: L 23–31' -> 'usc')."""
    n = re.sub(r"\(.*?\)", "", str(name))
    n = re.split(r"[,;]", n, maxsplit=1)[0].strip().lower()
    return re.sub(r"^(at|vs\.?|versus)\s+", "", n).strip()


def played_and_listed(schedule, games, today, season):
    """Schedule rows dated before today whose opponent is already in the results: the game was added to the results but not removed
    from the remaining schedule (or, if it was a second game against the same team, its own result is missing). Future rows against a
    team already played are left alone, because they can be genuine rematches."""
    teams = {_team(g.get("opp", "")) for g in games if isinstance(g, dict)}
    out = []
    for r in schedule:
        d = game_date(r[0], season) if isinstance(r, (list, tuple)) and r else None
        if d is not None and d < today and _team(r[1] if len(r) > 1 else "") in teams:
            out.append(r)
    return out


def _count(v, minimum):
    return isinstance(v, int) and not isinstance(v, bool) and v >= minimum


def watch_coverage(D, label):
    """The stated coverage of one number to watch, as {"through_week": n, "games": n} (either may be absent), or None when the data do
    not state it. Malformed values are ignored here (check_data reports them), so a bad entry never shows as coverage."""
    meta = D.get("meta") if isinstance(D.get("meta"), dict) else {}
    cov = meta.get("coverage") if isinstance(meta.get("coverage"), dict) else {}
    raw = cov.get("watch")
    if _count(raw, 1):
        return {"through_week": raw}  # one week stated for every number to watch
    if isinstance(raw, dict) and isinstance(raw.get(label), dict):
        e = raw[label]
        out = {k: e[k] for k, low in (("through_week", 1), ("games", 0)) if _count(e.get(k), low)}
        return out or None
    return None


def watch_coverage_line(D, label):
    """The line under a watch card: what its data say it covers, or 'Coverage not specified'."""
    c = watch_coverage(D, label)
    if not c:
        return "Coverage not specified"
    parts = []
    if "games" in c:
        parts.append(count_words(c["games"], "completed game"))
    if "through_week" in c:
        parts.append(f"through week {c['through_week']}")
    line = "Coverage: " + " ".join(parts)
    latest, _ = latest_game(D.get("games") or [])
    if "through_week" in c and latest is not None and c["through_week"] < _week(latest):
        line += f" (the results include week {_week(latest)})"
    return line


def coverage(D):
    """{section: week} from meta.coverage, keeping only whole-number weeks."""
    cov = (D.get("meta") or {}).get("coverage") if isinstance(D.get("meta"), dict) else None
    if not isinstance(cov, dict):
        return {}
    return {k: v for k, v in cov.items() if isinstance(v, int) and not isinstance(v, bool)}


def coverage_note(D, section):
    """One line for under a section: the week it is through, or that its coverage is not stated."""
    cov = coverage(D).get(section)
    name = SECTIONS[section]
    if cov is None:
        return f"{name}: the data do not say which week these are through, so they may not include the latest game."
    latest, _ = latest_game(D.get("games") or [])
    if latest is not None and cov < _week(latest):
        return f"{name}: through week {cov}. The results include week {_week(latest)}, so these do not include the latest game yet."
    return f"{name}: through week {cov}."


def last_successful_refresh(D):
    """meta.last_successful_refresh when it is a valid ISO 8601 date or date-time, else None (absent or unreadable: never guessed)."""
    meta = D.get("meta") if isinstance(D.get("meta"), dict) else {}
    v = meta.get("last_successful_refresh")
    if not isinstance(v, str) or not v.strip():
        return None
    for parse in (datetime.fromisoformat, date.fromisoformat):
        try:
            parse(v.strip())
            return v.strip()
        except ValueError:
            continue
    return None


def section_freshness(D, section):
    """What the data state about one section's freshness, and whether it is stale. Stale means the data say so: the section's stated coverage
    week is earlier than the latest result, or the builder's note for the section starts "NOT refreshed". Nothing is inferred from the snapshot
    date, and "up to date" only ever means "with the latest result in this data file", not with the real world.
    Returns {"cutoff_week", "stated", "status", "reasons", "snapshot", "last_refresh"}; status is "stale", "up to date" or "not stated"."""
    meta = D.get("meta") if isinstance(D.get("meta"), dict) else {}
    week = coverage(D).get(section)
    notes = meta.get("freshness") if isinstance(meta.get("freshness"), dict) else {}
    stated = notes.get(section).strip() if isinstance(notes.get(section), str) and notes.get(section).strip() else None
    latest, _ = latest_game(D.get("games") or [])
    latest_week = _week(latest) if latest is not None else None
    reasons = []
    if week is not None and latest_week is not None and week < latest_week:
        reasons.append(f"it covers through week {week}, but the results include week {latest_week}")
    if stated and stated.lower().startswith("not refreshed"):
        reasons.append("the data file says this section was not refreshed")
    if reasons:
        status = "stale"
    elif week is not None and latest_week is not None:
        status = "up to date"
    else:
        status = "not stated"
    snapshot = meta.get("snapshot") if isinstance(meta.get("snapshot"), str) and meta.get("snapshot").strip() else None
    return {"cutoff_week": week, "stated": stated, "status": status, "reasons": reasons, "snapshot": snapshot,
            "last_refresh": last_successful_refresh(D)}


PLAYER_STATUSES = ("current", "transferred", "departed", "unknown")


_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def name_key(name):
    """A player's name for matching across sources: case, accents, punctuation and a trailing Jr./Sr./II/III are ignored
    ('LaVar Arrington II' and 'Lavar Arrington' match; 'Jeff Exinor Jr.' and 'Jeff Exinor' match). Different first or last names never match."""
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower()
    parts = re.sub(r"[^a-z0-9 ]+", " ", s.replace("'", "").replace("’", "")).split()
    while len(parts) > 2 and parts[-1] in _SUFFIXES:
        parts.pop()
    return " ".join(parts)


def roster_snapshot(obj, season, today):
    """A validated roster snapshot ({"season", "as_of", "players": [{"id", "name", "recruit_class", ...}], "provenance"}), or (None, problem).
    It is used only for the current season, only if its date is not in the future, and only if no athlete id appears twice."""
    if obj is None:
        return None, None
    if not isinstance(obj, dict) or not isinstance(obj.get("players"), list) or not obj["players"]:
        return None, "The roster snapshot is malformed; roster status was not taken from it."
    if obj.get("season") != season:
        return None, f"The roster snapshot is for {obj.get('season')}, not {season}; roster status was not taken from it."
    try:
        as_of = date.fromisoformat(str(obj.get("as_of", "")))
    except ValueError:
        return None, "The roster snapshot has no valid as_of date; roster status was not taken from it."
    if as_of > today:
        return None, f"The roster snapshot is dated {as_of.isoformat()}, after today; roster status was not taken from it."
    players = [p for p in obj["players"] if isinstance(p, dict) and isinstance(p.get("name"), str) and p["name"].strip()]
    ids = [str(p.get("id")) for p in players if p.get("id") is not None]
    if len(players) != len(obj["players"]) or len(ids) != len(set(ids)):
        return None, "The roster snapshot has unnamed players or repeated athlete ids; roster status was not taken from it."
    return {**obj, "as_of": as_of.isoformat(), "players": players}, None


def player_status(D, recorded=None, roster=None):
    """Roster status of each player in the 2025-class forecast list. Sources, each giving a status with a verification date:
      1. the data file's optional "watchClassStatus": {"Player Name": {"status": "current" | "transferred" | "departed" | "unknown",
         "verified": "YYYY-MM-DD", "source": "..."}}
      2. `recorded`: the same mapping from roster_status.json in this repository (dated records such as a confirmed transfer)
      3. `roster`: a roster snapshot validated by roster_snapshot(). On it: current (verified on its as_of date); not on it: departed;
         two roster players with the same name: unknown, flagged.
    The latest verification date wins; on a tie the earlier source in this list wins. Names are matched with name_key(). Names in
    roster_status.json that are not in this forecast list are skipped silently, because the list in the data file may differ.
    Returns ({player: {"status", "verified", "source"}}, problems). A player with no valid entry from any source is "not verified". An entry
    needs a known status AND a valid date to count. Nothing is inferred beyond the roster itself, and the forecast is never changed: a status
    only decides which group the original prediction is listed under."""
    players = [r[0] for r in D.get("watchClass") or [] if isinstance(r, (list, tuple)) and r]
    out = {p: {"status": "not verified", "verified": None, "source": None} for p in players}
    problems = []
    by_key = {}
    for p in players:
        by_key.setdefault(name_key(p), []).append(p)
    for k, same in by_key.items():
        if len(same) > 1:
            problems.append(f"The forecast list has {len(same)} entries for one player ({', '.join(map(repr, same))}); their status is shown as "
                            "unknown until the list is corrected.")

    def put(name, status, verified, source):
        if out[name]["verified"] is not None and out[name]["verified"] >= verified:
            return  # an equal or later check is already recorded
        out[name] = {"status": status, "verified": verified, "source": source}

    for raw, where, strict in ((D.get("watchClassStatus"), "watchClassStatus", True), (recorded, "roster_status.json", False)):
        if raw is None:
            continue
        if not isinstance(raw, dict):
            problems.append(f"{where} should map each player's name to {{status, verified, source}}; it was ignored.")
            continue
        for name, e in raw.items():
            match = by_key.get(name_key(name), [])
            if len(match) != 1:
                if strict and not match:
                    problems.append(f"{where} names {name!r}, who is not in the forecast list; ignored.")
                continue
            if not isinstance(e, dict) or e.get("status") not in PLAYER_STATUSES:
                problems.append(f"{where}[{name!r}].status should be one of {', '.join(PLAYER_STATUSES)}; shown as not verified.")
                continue
            try:
                verified = date.fromisoformat(str(e.get("verified", ""))).isoformat()
            except ValueError:
                problems.append(f"{where}[{name!r}].verified should be a date (YYYY-MM-DD); shown as not verified.")
                continue
            put(match[0], e["status"], verified, e.get("source") if isinstance(e.get("source"), str) and e.get("source").strip() else None)
    if roster is not None:
        on = {}
        for r in roster["players"]:
            on.setdefault(name_key(r["name"]), []).append(r)
        label = f"the {roster['season']} roster snapshot (as of {roster['as_of']}; {(roster.get('provenance') or {}).get('source', 'source not recorded')})"
        for k, names in by_key.items():
            if len(names) != 1:
                continue
            hits = on.get(k, [])
            # not found by name, but a roster player has the same last name and first initial ('Josh' for 'Joshua'): never call that a departure
            near = [r["name"] for key, rs in on.items() for r in rs
                    if not hits and key.split()[-1:] == k.split()[-1:] and key[:1] == k[:1]]
            if len(hits) == 1:
                put(names[0], "current", roster["as_of"], f"On {label}.")
            elif near:
                put(names[0], "unknown", roster["as_of"], f"Not on {label} under this name; possible match: {', '.join(near)}. Not resolved.")
            elif not hits:
                put(names[0], "departed", roster["as_of"], f"Not on {label}.")
            else:
                put(names[0], "unknown", roster["as_of"], f"{len(hits)} players on {label} share this name; not resolved.")
    for k, names in by_key.items():
        if len(names) > 1:
            for n in names:
                out[n] = {"status": "unknown", "verified": None, "source": "Listed more than once in the forecast list."}
    return out, problems


def unscored_class_members(D, roster, recruit_class):
    """Players on the roster snapshot from the forecast's recruiting class (high-school recruits) who are not in the forecast list. The list's
    model and selection rule are not recorded, so no chance can be computed for them here; they are listed so the gap is visible."""
    if roster is None:
        return []
    listed = {name_key(r[0]) for r in D.get("watchClass") or [] if isinstance(r, (list, tuple)) and r}
    return [r for r in roster["players"] if r.get("recruit_class") == recruit_class and r.get("recruit_type") in (None, "HighSchool")
            and name_key(r["name"]) not in listed]


def star_series(traj, keys):
    """The development-chart series `keys` from a traj block ({"years": [...], key: [...], optional "players": {key: [...]}}), or None if any
    is missing or malformed: every series must have one value (a number, or null for no players) per year. Values are used as given;
    nothing is filled in, split or estimated. Player counts are returned only when complete for that series."""
    if not isinstance(traj, dict):
        return None
    years = traj.get("years")
    if not isinstance(years, list) or not years or not all(_count(y, 1) for y in years):
        return None
    out = {"years": years, "players": {}}
    counts = traj.get("players") if isinstance(traj.get("players"), dict) else {}
    for k in keys:
        v = traj.get(k)
        if not isinstance(v, list) or len(v) != len(years) or not all(x is None or (isinstance(x, (int, float)) and not isinstance(x, bool)) for x in v):
            return None
        out[k] = v
        n = counts.get(k)
        if isinstance(n, list) and len(n) == len(years) and all(_count(x, 0) for x in n):
            out["players"][k] = n
    return out


def games_through(D, week):
    """How many games in the results were played in or before the given week."""
    return sum(1 for g in D.get("games") or [] if _week(g) is not None and _week(g) <= week)


def check_data(D, today, season):
    """Messages describing anything inconsistent or missing in the data. Empty when nothing is found. Each message says what to fix."""
    out = []
    missing = [k for k in REQUIRED if k not in D]
    if missing:
        out.append(f"Missing from the data file: {', '.join(missing)}. Pages that use them cannot be shown until they are added.")

    meta = D.get("meta") if isinstance(D.get("meta"), dict) else {}
    lack = [k for k in META_FIELDS if k not in meta]
    if "meta" in D and lack:
        out.append(f"The data's meta section is missing {', '.join(lack)}.")
    tw = meta.get("through_week")
    if "through_week" in meta and (not isinstance(tw, int) or isinstance(tw, bool)):
        out.append(f"meta.through_week should be a whole week number; it is {tw!r}.")
        tw = None

    games = D.get("games") if isinstance(D.get("games"), list) else []
    for i, g in enumerate(games, start=1):
        if not isinstance(g, dict):
            out.append(f"Result row {i} is not a game record.")
            continue
        lack = [k for k in GAME_FIELDS if k not in g]
        label = f"Result row {i} ({g.get('opp', 'no opponent')})"
        if lack:
            out.append(f"{label} is missing {', '.join(lack)}.")
        if "wk" in g and _week(g) is None:
            out.append(f"{label} has no whole-number week ({g.get('wk')!r}); it is left out of the week-by-week chart and cannot be the latest game.")

    weeks = [_week(g) for g in games if _week(g) is not None]
    for w in sorted({w for w in weeks if weeks.count(w) > 1}):
        out.append(f"Week {w} appears {weeks.count(w)} times in the results. Remove the duplicate, or correct the week number.")
    if weeks != sorted(weeks):
        out.append("The results are not in week order. The dashboard uses the highest week as the latest game, but the file should be sorted.")

    latest, problem = latest_game(games)
    if problem and games:
        out.append(f"The latest game cannot be identified: {problem}.")
    if latest is not None and tw is not None and tw < _week(latest):
        out.append(f"The header says data through week {tw}, but the results include week {_week(latest)}. Update meta.through_week.")

    sched = D.get("schedule") if isinstance(D.get("schedule"), list) else []
    for r in played_and_listed(sched, games, today, season):
        out.append(f"{r[1]} ({r[0]}) is in both the results and the remaining schedule. Remove it from the schedule; if it was a second game "
                   f"against the same team, add that game's result.")

    watch = D.get("watch") if isinstance(D.get("watch"), list) else []
    for i, x in enumerate(watch, start=1):
        lack = [k for k in WATCH_FIELDS if not isinstance(x, dict) or k not in x]
        if lack:
            out.append(f"Number to watch {i} is missing {', '.join(lack)}.")

    raw = meta.get("coverage")
    if raw is not None and not isinstance(raw, dict):
        out.append("meta.coverage should map sections to weeks, for example {\"watch\": 6, \"transfers\": 6}.")
    elif isinstance(raw, dict):
        for k, v in raw.items():
            if k not in SECTIONS:
                out.append(f"meta.coverage has an unknown section {k!r}; known sections are {', '.join(SECTIONS)}.")
            elif k == "watch" and isinstance(v, dict):
                out += _check_watch_coverage(v, watch, games, latest, tw)
            elif not isinstance(v, int) or isinstance(v, bool):
                out.append(f"meta.coverage.{k} should be a whole week number; it is {v!r}." if k != "watch" else
                           f"meta.coverage.watch should be one week number or a map from a card's label to its coverage; it is {v!r}.")
    for k, v in coverage(D).items():
        if k in SECTIONS and latest is not None and v < _week(latest):
            out.append(f"{SECTIONS[k]} are through week {v}, but the results include week {_week(latest)}. Update them, then meta.coverage.{k}.")
        if k in SECTIONS and tw is not None and v > tw:
            out.append(f"{SECTIONS[k]} say week {v}, later than the header's week {tw}. Check meta.through_week and meta.coverage.{k}.")
    return out


def _check_watch_coverage(cov, watch, games, latest, tw):
    """Messages for a per-card meta.coverage.watch map: unknown or duplicated labels, malformed entries, and coverage
    that contradicts the results or the header. None of these change a card; a card whose entry is malformed shows 'Coverage not specified'."""
    out = []
    labels = [x.get("label") for x in watch if isinstance(x, dict) and "label" in x]
    for lab in sorted({l for l in labels if labels.count(l) > 1}, key=str):
        out.append(f"Two numbers to watch share the label {lab!r}, so their coverage cannot be told apart. Give each a distinct label.")
    for lab, e in cov.items():
        where = f"meta.coverage.watch[{lab!r}]"
        if lab not in labels:
            out.append(f"{where} does not match any number to watch (labels: {', '.join(map(str, labels))}). Check the spelling.")
            continue
        if not isinstance(e, dict) or not e:
            out.append(f"{where} should look like {{\"through_week\": 6, \"games\": 6}}; it is {e!r}.")
            continue
        extra = [k for k in e if k not in ("through_week", "games")]
        if extra:
            out.append(f"{where} has unknown keys {', '.join(map(str, extra))}; use through_week and games.")
        wk, n = e.get("through_week"), e.get("games")
        if "through_week" in e and not _count(wk, 1):
            out.append(f"{where}.through_week should be a whole week number of 1 or more; it is {wk!r}.")
            wk = None
        if "games" in e and not _count(n, 0):
            out.append(f"{where}.games should be a whole number of games; it is {n!r}.")
            n = None
        if wk is not None and n is not None and n > wk:
            out.append(f"{where} says {n} games through week {wk}, but Penn State plays at most one game a week.")
        if wk is not None and n is not None:
            listed = sum(1 for g in games if _week(g) is not None and _week(g) <= wk and isinstance(g, dict) and g.get("res") in ("W", "L", "T"))
            if n > listed:
                out.append(f"{where} says {n} games through week {wk}, but the results list only {listed} completed games by week {wk}.")
        if wk is not None and tw is not None and wk > tw:
            out.append(f"{lab} says week {wk}, later than the header's week {tw}. Check meta.through_week and {where}.")
        if wk is not None and latest is not None and wk < _week(latest):
            out.append(f"{lab} is through week {wk}, but the results include week {_week(latest)}. Update it, then {where}.")
    return out


def fetch_with_retry(url, fetch, failures, now, wait=RETRY_WAIT):
    """Read the data link. `fetch(url)` returns the data or raises; `failures` maps a link to when it last failed, shared by every viewer.
    A failure is not remembered as data: the link is tried again on a later page load once `wait` seconds have passed, so a broken link
    does not cost every page load (and every click) a ten-second timeout. Returns (data or None, note or None)."""
    last = failures.get(url)
    if last is not None and now - last < wait:
        return None, f"data_url could not be read a moment ago; it will be tried again in about {max(1, round(wait - (now - last)))} seconds"
    try:
        d = fetch(url)
        if not isinstance(d, dict) or not d:  # an empty object {} has no dashboard data; fall back as for any other failure
            raise ValueError("not a non-empty JSON object")
    except Exception as ex:
        failures[url] = now
        return None, f"data_url was set but could not be read ({type(ex).__name__})"
    failures.pop(url, None)
    return d, None
