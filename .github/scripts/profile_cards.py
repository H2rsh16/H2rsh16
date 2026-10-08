#!/usr/bin/env python3
"""Generates themed (dark + light) SVG cards for the profile README:
   - activity-{dark,light}.svg  : last 30 days contribution graph
   - progress-{dark,light}.svg  : stats tiles + language bar
Data comes from the GitHub GraphQL API (public data, no manual input).

Env:  GH_USER (required), GH_TOKEN (required unless --mock)
Usage: python profile_cards.py <out_dir> [--mock]
"""
import json, os, sys, random, datetime as dt, urllib.request
from xml.sax.saxutils import escape

FONT = '-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans",Helvetica,Arial,sans-serif'

# GitHub's own palette (Primer). Change "accent" to restyle everything.
THEMES = {
    "dark": dict(bg="#0d1117", card="#161b22", border="#30363d", text="#e6edf3",
                 muted="#8b949e", accent="#2f81f7", grid="#21262d", dot_bg="#0d1117"),
    "light": dict(bg="#ffffff", card="#f6f8fa", border="#d0d7de", text="#1f2328",
                  muted="#656d76", accent="#0969da", grid="#d8dee4", dot_bg="#ffffff"),
}

QUERY = """
query($login:String!){
  user(login:$login){
    followers{totalCount}
    pullRequests{totalCount}
    issues{totalCount}
    repositories(ownerAffiliation:OWNER,isFork:false,first:100){
      totalCount
      nodes{ stargazerCount
        languages(first:6,orderBy:{field:SIZE,direction:DESC}){edges{size node{name color}}}}
    }
    contributionsCollection{
      totalCommitContributions
      totalPullRequestReviewContributions
      contributionCalendar{ totalContributions
        weeks{contributionDays{date contributionCount}} }
    }
  }
}"""


def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "profile-cards"})
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload or not payload.get("data", {}).get("user"):
        raise SystemExit(f"GraphQL error: {payload.get('errors')}")
    return payload["data"]["user"]


def mock():
    random.seed(7)
    today = dt.date.today()
    days = [{"date": str(today - dt.timedelta(days=364 - i)),
             "contributionCount": random.choice([0, 0, 1, 2, 3, 5, 8, 4, 0, 2])} for i in range(365)]
    weeks = [{"contributionDays": days[i:i + 7]} for i in range(0, 365, 7)]
    langs = [("Java", "#b07219", 50), ("Python", "#3572A5", 30), ("JavaScript", "#f1e05a", 22),
             ("TypeScript", "#3178c6", 12), ("Kotlin", "#A97BFF", 6)]
    return {"followers": {"totalCount": 24}, "pullRequests": {"totalCount": 31},
            "issues": {"totalCount": 9},
            "repositories": {"totalCount": 28, "nodes": [
                {"stargazerCount": 17, "languages": {"edges": [
                    {"size": s * 1000, "node": {"name": n, "color": c}} for n, c, s in langs]}}]},
            "contributionsCollection": {
                "totalCommitContributions": 612, "totalPullRequestReviewContributions": 14,
                "contributionCalendar": {"totalContributions": sum(d["contributionCount"] for d in days),
                                         "weeks": weeks}}}


def flat_days(u):
    cal = u["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = [d for w in cal for d in w["contributionDays"]]
    today = str(dt.date.today())
    return [d for d in days if d["date"] <= today]


def streaks(days):
    longest = run = 0
    for d in days:
        run = run + 1 if d["contributionCount"] > 0 else 0
        longest = max(longest, run)
    cur, i = 0, len(days) - 1
    if i >= 0 and days[i]["contributionCount"] == 0:
        i -= 1  # today may not have contributions yet
    while i >= 0 and days[i]["contributionCount"] > 0:
        cur += 1
        i -= 1
    return cur, longest


def fmt(n):
    return f"{n/1000:.1f}k" if n >= 10000 else f"{n:,}"


def svg_open(w, h, t, extra_css=""):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" fill="none" role="img">
<style>
text{{font-family:{FONT}}}
{extra_css}
</style>
<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="10" fill="{t['card']}" stroke="{t['border']}"/>'''


# ----------------------------------------------------------------- activity
def activity_svg(u, t):
    W, H = 850, 210
    days = flat_days(u)[-30:]
    vals = [d["contributionCount"] for d in days]
    total = sum(vals)
    top = max(4, -(-max(vals) // 4) * 4)  # round up to a multiple of 4 -> clean y labels
    x0, x1, y0, y1 = 52, W - 28, 62, H - 38
    n = len(vals)
    xs = [x0 + i * (x1 - x0) / (n - 1) for i in range(n)]
    ys = [y1 - v / top * (y1 - y0) for v in vals]

    path = f"M{xs[0]:.1f},{ys[0]:.1f}"
    for i in range(1, n):
        mx = (xs[i - 1] + xs[i]) / 2
        path += f" C{mx:.1f},{ys[i-1]:.1f} {mx:.1f},{ys[i]:.1f} {xs[i]:.1f},{ys[i]:.1f}"
    area = f"{path} L{xs[-1]:.1f},{y1} L{xs[0]:.1f},{y1} Z"

    css = f"""
@keyframes draw{{from{{stroke-dasharray:1;stroke-dashoffset:1}}to{{stroke-dasharray:1;stroke-dashoffset:0}}}}
@keyframes fade{{from{{opacity:0}}to{{opacity:1}}}}
@keyframes pop{{from{{opacity:0;transform:scale(0)}}to{{opacity:1;transform:scale(1)}}}}
@keyframes pulse{{0%{{r:4;opacity:.5}}100%{{r:12;opacity:0}}}}
.line{{animation:draw 2.2s ease-out both}}
.area{{animation:fade 1.6s ease-out .6s both}}
.dot{{transform-box:fill-box;transform-origin:center;animation:pop .35s ease-out both}}
.pulse{{animation:pulse 2s ease-out 2.4s infinite}}
"""
    o = [svg_open(W, H, t, css)]
    o.append(f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
             f'<stop offset="0" stop-color="{t["accent"]}" stop-opacity=".35"/>'
             f'<stop offset="1" stop-color="{t["accent"]}" stop-opacity="0"/></linearGradient></defs>')
    o.append(f'<text x="24" y="34" font-size="15" font-weight="600" fill="{t["text"]}">Last 30 days</text>')
    o.append(f'<text x="{W-24}" y="34" font-size="13" text-anchor="end" fill="{t["muted"]}">contributions</text>')
    o.append(f'<text x="{W-24-92}" y="34" font-size="13" text-anchor="end" font-weight="700" fill="{t["accent"]}">{total}</text>')
    for k in range(5):  # grid + y labels
        gy = y0 + k * (y1 - y0) / 4
        o.append(f'<line x1="{x0}" x2="{x1}" y1="{gy:.1f}" y2="{gy:.1f}" stroke="{t["grid"]}" stroke-dasharray="3 4"/>')
        o.append(f'<text x="{x0-10}" y="{gy+4:.1f}" font-size="11" text-anchor="end" fill="{t["muted"]}">'
                 f'{round(top - k * top / 4)}</text>')
    step = 5
    for i in range(0, n, step):
        d = dt.date.fromisoformat(days[i]["date"])
        o.append(f'<text x="{xs[i]:.1f}" y="{H-14}" font-size="11" text-anchor="middle" fill="{t["muted"]}">'
                 f'{d.strftime("%b")} {d.day}</text>')
    o.append(f'<path class="area" d="{area}" fill="url(#g)"/>')
    o.append(f'<path class="line" pathLength="1" d="{path}" stroke="{t["accent"]}" stroke-width="2.5" '
             f'stroke-linecap="round" stroke-linejoin="round"/>')
    for i, (x, y) in enumerate(zip(xs, ys)):
        o.append(f'<circle class="dot" style="animation-delay:{0.5 + i*0.06:.2f}s" cx="{x:.1f}" cy="{y:.1f}" r="3.5" '
                 f'fill="{t["dot_bg"]}" stroke="{t["accent"]}" stroke-width="2"/>')
    o.append(f'<circle class="pulse" cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="4" fill="{t["accent"]}"/>')
    o.append("</svg>")
    return "\n".join(o)


# ----------------------------------------------------------------- progress
def progress_svg(u, t):
    W, H = 850, 215
    cc = u["contributionsCollection"]
    days = flat_days(u)
    cur, longest = streaks(days)
    stars = sum(r["stargazerCount"] for r in u["repositories"]["nodes"])
    tiles = [
        ("Contributions", cc["contributionCalendar"]["totalContributions"], "last year"),
        ("Commits", cc["totalCommitContributions"], "last year"),
        ("Pull Requests", u["pullRequests"]["totalCount"], "all time"),
        ("Stars", stars, "earned"),
        ("Followers", u["followers"]["totalCount"], "on GitHub"),
        ("Streak", f"{cur}d", f"longest {longest}d"),
    ]
    css = f"""
@keyframes rise{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:translateY(0)}}}}
@keyframes grow{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}
.tile{{animation:rise .6s ease-out both}}
.bar{{transform-origin:24px 0;animation:grow 1.4s cubic-bezier(.2,.8,.2,1) .5s both}}
"""
    o = [svg_open(W, H, t, css)]
    o.append(f'<text x="24" y="34" font-size="15" font-weight="600" fill="{t["text"]}">Progress</text>')
    o.append(f'<text x="{W-24}" y="34" font-size="13" text-anchor="end" fill="{t["muted"]}">'
             f'{u["repositories"]["totalCount"]} repositories</text>')
    gap, tw = 12, (W - 48 - 12 * 5) / 6
    for i, (label, val, sub) in enumerate(tiles):
        x = 24 + i * (tw + gap)
        v = fmt(val) if isinstance(val, int) else val
        o.append(f'<g class="tile" style="animation-delay:{i*0.08:.2f}s">'
                 f'<rect x="{x:.1f}" y="52" width="{tw:.1f}" height="76" rx="8" fill="{t["bg"]}" stroke="{t["border"]}"/>'
                 f'<rect x="{x+12:.1f}" y="52" width="26" height="3" rx="1.5" fill="{t["accent"]}"/>'
                 f'<text x="{x+14:.1f}" y="76" font-size="11.5" fill="{t["muted"]}">{escape(label)}</text>'
                 f'<text x="{x+14:.1f}" y="103" font-size="24" font-weight="700" fill="{t["text"]}">{escape(str(v))}</text>'
                 f'<text x="{x+14:.1f}" y="120" font-size="10.5" fill="{t["muted"]}">{escape(sub)}</text></g>')

    # languages (by bytes across owned, non-fork repos)
    agg = {}
    for r in u["repositories"]["nodes"]:
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]
            a = agg.setdefault(n, [0, e["node"]["color"] or t["accent"]])
            a[0] += e["size"]
    top = sorted(agg.items(), key=lambda kv: -kv[1][0])[:6]
    tot = sum(v[0] for _, v in top) or 1
    o.append(f'<text x="24" y="156" font-size="12" font-weight="600" fill="{t["text"]}">Top languages</text>')
    bw = W - 48
    o.append(f'<clipPath id="c"><rect x="24" y="164" width="{bw}" height="8" rx="4"/></clipPath>')
    o.append(f'<rect x="24" y="164" width="{bw}" height="8" rx="4" fill="{t["grid"]}"/>')
    o.append('<g class="bar" clip-path="url(#c)">')
    x = 24.0
    for name, (size, color) in top:
        w = bw * size / tot
        o.append(f'<rect x="{x:.1f}" y="164" width="{max(w-1.5,1):.1f}" height="8" fill="{color}"/>')
        x += w
    o.append("</g>")
    lx = 24
    for name, (size, color) in top:
        pct = f"{100*size/tot:.1f}%"
        o.append(f'<circle cx="{lx+4}" cy="193" r="4" fill="{color}"/>'
                 f'<text x="{lx+14}" y="197" font-size="11.5" fill="{t["text"]}">{escape(name)} '
                 f'<tspan fill="{t["muted"]}">{pct}</tspan></text>')
        lx += 14 + (len(name) + len(pct) + 1) * 6.6 + 22
    o.append("</svg>")
    return "\n".join(o)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "dist"
    os.makedirs(out, exist_ok=True)
    u = mock() if "--mock" in sys.argv else fetch(os.environ["GH_USER"], os.environ["GH_TOKEN"])
    for name, t in THEMES.items():
        open(f"{out}/activity-{name}.svg", "w", encoding="utf-8").write(activity_svg(u, t))
        open(f"{out}/progress-{name}.svg", "w", encoding="utf-8").write(progress_svg(u, t))
    print("generated cards in", out)


if __name__ == "__main__":
    main()
