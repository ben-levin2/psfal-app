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


# Roster statuses (Step 2, rule R6). A status is about roster membership only: it never changes a probability, an original rank or a
# forecast's outcome, and a transfer or departure is not a failed prediction (the outcome cannot be observed at Penn State).
#   current                               on a dated current-season roster source (and on every other dated source checked)
#   not_on_roster_snapshot_unconfirmed    absent from ONE dated roster source; absence alone is never a departure
#   departed                              absent from two independent dated roster sources, or an explicit dated record
#   transferred                           an explicit dated portal or news record that names the destination
#   unknown                               ambiguous identity, roster sources that disagree, or a record marked unknown
#   not verified                          no source at all
PLAYER_STATUSES = ("current", "transferred", "departed", "unknown")  # statuses an explicit record may state
ROSTER_STATUSES = ("current", "not_on_roster_snapshot_unconfirmed", "departed", "transferred", "unknown")
STATUS_LABEL = {"current": "current", "not_on_roster_snapshot_unconfirmed": "not on roster snapshot (unconfirmed)", "departed": "departed",
                "transferred": "transferred", "unknown": "unknown", "not verified": "not verified"}


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


def forecast_class(obj, recruit_class):
    """A validated forecast-class record (forecast_class.json: every high-school recruit of the class with identity, rating, first-season
    and roster-check facts), or (None, problem). Repeated athlete ids or another class make it unusable."""
    if obj is None:
        return None, None
    if not isinstance(obj, dict) or not isinstance(obj.get("players"), list) or obj.get("recruit_class") != recruit_class:
        return None, f"The forecast-class record is not a valid record of the {recruit_class} class; it was not used."
    ids = [p.get("id") for p in obj["players"] if isinstance(p, dict)]
    if len(ids) != len(obj["players"]) or None in ids or len(set(ids)) != len(ids):
        return None, "The forecast-class record has players without ids or repeated ids; it was not used."
    return obj, None


def identity_note(snapshot_player, check):
    """Secondary identity check of one player found on both roster sources (matched by athlete id, never by jersey): a jersey or position
    group that differs is reported for human review. It never changes a status: numbers change and are shared (#11, #19)."""
    out = []
    a, b = snapshot_player.get("jersey"), check.get("jersey")
    if a is not None and b is not None and a != b:
        out.append(f"jersey differs (CFBD roster #{a}, official roster #{b})")
    ga, gb = position_group(snapshot_player.get("position")), position_group(check.get("position"))
    if check.get("position") and snapshot_player.get("position") and ga != gb:
        out.append(f"position group differs (CFBD {snapshot_player.get('position')} = {ga}, official {check.get('position')} = {gb})")
    return ("; ".join(out) + ". Secondary identity check only; needs human review. Status unchanged.") if out else None


def player_status(D, recorded=None, roster=None, klass=None):
    """Roster status of each player in the forecast list (see ROSTER_STATUSES). Evidence, each item dated:
      1. explicit records: the data file's optional "watchClassStatus", then `recorded` (roster_status.json), both
         {"Player Name": {"status": one of PLAYER_STATUSES, "verified": "YYYY-MM-DD", "source": "...", "destination": "..."}};
         "transferred" counts only with a destination;
      2. roster evidence: `roster` (a snapshot validated by roster_snapshot()) and, from `klass` (forecast_class()), each player's
         independent official-roster check. On every source: current. Absent from one: not_on_roster_snapshot_unconfirmed. Absent from two
         independent sources: departed. Sources that disagree: unknown.
    The latest date wins; on a tie the earlier item in this list wins. Identity: a forecast name is linked to ONE player of the class record
    by name_key(), then that player's athlete id is used to find him on the roster snapshot (ids before names). Two class players with one
    name, a near match on the roster ('Josh' for 'Joshua'), or a duplicate forecast entry give unknown, for review; nothing is guessed.
    Returns ({player: {"status", "verified", "source"}}, problems). A player with no evidence is "not verified"."""
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
            return  # an equal or later piece of evidence is already recorded
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
            if e["status"] == "transferred" and not (isinstance(e.get("destination"), str) and e["destination"].strip()):
                problems.append(f"{where}[{name!r}] says transferred but names no destination; ignored.")
                continue
            put(match[0], e["status"], verified, e.get("source") if isinstance(e.get("source"), str) and e.get("source").strip() else None)

    cls = {}
    for c in (klass or {}).get("players", []):
        cls.setdefault(name_key(c.get("name", "")), []).append(c)
    on_name, on_id = {}, {}
    for r in (roster or {}).get("players", []):
        on_name.setdefault(name_key(r["name"]), []).append(r)
        if r.get("id") is not None:
            on_id[str(r["id"])] = r
    snap = (f"the {roster['season']} CFBD roster snapshot (as of {roster['as_of']})" if roster else None)
    for k, names in by_key.items():
        if len(names) != 1:
            continue
        name = names[0]
        ids = cls.get(k, [])
        if len(ids) > 1:
            put(name, "unknown", max([roster["as_of"]] if roster else ["0000-01-01"]),
                f"{len(ids)} players of the class record share this name; identity needs review.")
            continue
        player = ids[0] if ids else None
        evidence = []  # (date, on roster?, description)
        if roster:
            if player is not None:
                listed = str(player["id"]) in on_id  # the athlete id decides; the name is not used
            else:
                hits = on_name.get(k, [])
                near = [r["name"] for key, rs in on_name.items() for r in rs
                        if not hits and key.split()[-1:] == k.split()[-1:] and key[:1] == k[:1]]
                if near or len(hits) > 1:
                    why = f"possible match: {', '.join(near)}" if near else f"{len(hits)} roster players share this name"
                    put(name, "unknown", roster["as_of"], f"Not matched on {snap}: {why}. Identity needs review.")
                    continue
                listed = len(hits) == 1
            evidence.append((roster["as_of"], listed, f"{'On' if listed else 'Not on'} {snap}"))
        chk = (player or {}).get("official_roster_check")
        if roster and player is not None and isinstance(chk, dict) and chk.get("listed") and str(player["id"]) in on_id:
            note = identity_note(on_id[str(player["id"])], chk)
            if note:
                problems.append(f"{name}: {note}")
        if isinstance(chk, dict) and chk.get("date"):
            evidence.append((chk["date"], bool(chk.get("listed")), f"{'Listed' if chk.get('listed') else 'Not listed'} on the official "
                                                                      f"{chk.get('season', '')} roster (checked {chk['date']}: {chk.get('source', 'source not recorded')})"))
        if not evidence:
            continue
        latest = max(d for d, _, _ in evidence)
        text = "; ".join(t for _, _, t in evidence) + "."
        if all(on for _, on, _ in evidence):
            put(name, "current", latest, text)
        elif not any(on for _, on, _ in evidence):
            put(name, "departed" if len(evidence) >= 2 else "not_on_roster_snapshot_unconfirmed", latest, text)
        else:
            put(name, "unknown", latest, text + " The sources disagree; needs review.")
    for k, names in by_key.items():
        if len(names) > 1:
            for n in names:
                out[n] = {"status": "unknown", "verified": None, "source": "Listed more than once in the forecast list."}
    return out, problems


# Roster position -> PSFAL position group, as the pipeline maps it (psfal.tables.pos_group; EDGE/SDE/WDE with DL is the pipeline's assumption).
_POSITION_GROUP = {"QB": ["QB", "PRO", "DUAL"], "RB": ["RB", "FB", "HB", "APB"], "WR": ["WR"], "TE": ["TE"],
                   "OL": ["OL", "OT", "OG", "OC", "C", "G", "T", "IOL"], "DL": ["DL", "DT", "DE", "NT", "EDGE", "SDE", "WDE"],
                   "LB": ["LB", "ILB", "OLB"], "DB": ["CB", "S", "DB", "SS", "FS"], "ST": ["K", "P", "PK", "LS"], "ATH": ["ATH"]}


def position_group(position):
    """The PSFAL position group of a roster position ('DE' -> 'DL', 'CB' and 'S' -> 'DB', 'K' -> 'ST'); 'OTHER' if unknown."""
    p = str(position or "").upper().strip()
    return next((g for g, members in _POSITION_GROUP.items() if p in members), "OTHER")


# Position groups the PSFAL production measure covers (psfal.modules.development.PRIMARY); the forecast's first-season production input
# exists only for these.
MEASURABLE_GROUPS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
# Step 2, rule R4. The four states of a player's first-season production on the PSFAL measure:
#   recorded_positive   a CFBD season-stat row exists and the position's primary stat is above zero
#   recorded_zero       a CFBD season-stat row exists and the primary stat is zero, negative or not among the categories it records (CFBD
#                       lists only the categories a player recorded, so a row without the primary category is a recorded zero for it)
#   no_stat_row         no CFBD season-stat row: UNKNOWN. It is not zero and it does not mean the player did not play (redshirt, injury,
#                       no snaps and a data gap all look the same); the PSFAL pipeline's production_table fills it with zero, so its
#                       percentile is not a measurement
#   not_measurable      the position has no production measure in public data (offensive line, specialists, athletes, other)
PRODUCTION_STATES = ("recorded_positive", "recorded_zero", "no_stat_row", "not_measurable")


def production_state(player):
    """The first-season production state (PRODUCTION_STATES) of a forecast-class player record. Never converts a missing row to zero."""
    if player.get("group") not in MEASURABLE_GROUPS:
        return "not_measurable"
    first = player.get("first_season")
    if not isinstance(first, dict) or not first.get("has_stat_row"):
        return "no_stat_row"
    v = first.get("primary_value")
    if v is None:
        return "recorded_zero"
    return "recorded_positive" if v > 0 else "recorded_zero"


def eligibility(player, recruit_class):
    """Step 2 eligibility (rules R1, R2, R3, R5, R7) of a forecast-class player record: {"decision": "eligible" | "ineligible" | "review",
    "reason": "..."}. For audit counts and explanations only: it never scores a player or changes a forecast. First-season production is
    reported separately by production_state(), because how to treat an unknown (no_stat_row) is not decided yet."""
    def res(decision, reason):
        return {"decision": decision, "reason": reason}
    if player.get("recruit_class") != recruit_class or player.get("recruit_type") != "HighSchool":
        return res("ineligible", f"Not a high-school recruit of the {recruit_class} class.")
    method = player.get("match_method")
    if method == "name":
        return res("review", "Linked to the roster by name only; identity needs review.")
    if method not in ("athlete_id", "recruit_id") or not player.get("id"):
        return res("ineligible", "No roster identity link (athlete id or recruit id).")
    group = player.get("group")
    if group not in MEASURABLE_GROUPS:
        what = {"OL": "offensive line", "ST": "specialist (kicker, punter or snapper)", "ATH": "athlete without a set position"}.get(group, "other")
        return res("ineligible", f"Not forecastable with public production data: {what}.")
    chk = player.get("official_roster_check")
    if isinstance(chk, dict) and chk.get("position") and position_group(chk["position"]) != group:
        return res("review", f"Position group differs between CFBD ({group}) and the official roster ({chk['position']} = "
                             f"{position_group(chk['position'])}); needs review.")
    if player.get("rating") is None:
        return res("ineligible", "Missing recruiting rating.")
    if not isinstance(player.get("first_season"), dict):
        return res("ineligible", f"Not on the roster in {recruit_class}, so there is no first program season.")
    if player.get("arrival_uncertain") or player.get("first_roster_season") != recruit_class:
        return res("review", "First program season not confirmed by the roster; needs review.")
    return res("eligible", "Meets the population, identity, position, rating and first-season rules.")


NO_RECORDED_PRODUCTION = "No recorded first-season production — unknown; eligibility/scoring treatment pending."


def unscored_reason(player, recruit_class=2025):
    """Why a current player of the forecast's class has no forecast: the eligibility reason, or for an eligible player his production
    state. It names the missing input or rule; it never implies that a player without a stat row has known production."""
    e = eligibility(player, recruit_class)
    if e["decision"] != "eligible":
        return e["reason"] if e["decision"] == "ineligible" else f"Needs review: {e['reason']}"
    if production_state(player) == "no_stat_row":
        return NO_RECORDED_PRODUCTION
    return ("Recorded first-season production; not in the original list, whose model and selection rule are not recorded, so no chance is "
            "computed here.")


def unscored_class_members(D, roster, recruit_class, klass=None):
    """Current players of the forecast's class (on the roster snapshot, matched to the class record by athlete id) who are not in the
    forecast list, as class-record player dicts. Without a class record, roster players of the class are returned as they are. No chance is
    computed for them: the list's model and selection rule are not recorded."""
    if roster is None:
        return []
    listed = {name_key(r[0]) for r in D.get("watchClass") or [] if isinstance(r, (list, tuple)) and r}
    by_id = {str(c["id"]): c for c in (klass or {}).get("players", [])}
    out = []
    for r in roster["players"]:
        c = by_id.get(str(r.get("id")))
        if c is None and (klass or r.get("recruit_class") != recruit_class or r.get("recruit_type") not in (None, "HighSchool")):
            continue
        p = c or r
        if name_key(p["name"]) not in listed:
            out.append(p)
    return out


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
