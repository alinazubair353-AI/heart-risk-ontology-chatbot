"""Draw the whole ontology as a graph. No installs needed (standard library only).

    python graph_ontology.py

Creates ontology_graph.html (open it in the browser; right-click the picture to save it).
Left to right:  Patient -> base findings -> combined findings -> summary classes.
Solid arrow  = subclass link (child is a narrower class of the parent)
Dashed arrow = "defined using": the class definition uses the other class
Colour       = severity (grey info, yellow moderate, orange high, red urgent)
"""
import os
import sys

from ontology_engine import Ontology

HERE = os.path.dirname(os.path.abspath(__file__))
OWL = os.path.join(HERE, "heart_risk.owl")
OUT = os.path.join(HERE, "ontology_graph.html")

COLORS = {"info": "#d9dee5", "moderate": "#ffe08a", "high": "#ffb066", "urgent": "#ff7b7b"}
CAT_ORDER = ["lipids", "blood pressure", "glucose", "weight", "lifestyle", "history", "age",
             "symptom", "combined", "summary"]
BOX_W, BOX_H, X_GAP, Y_GAP = 300, 34, 120, 14


def refs(expr):
    if expr[0] == "ref":
        return [expr[1]] if expr[1] != "Patient" else []
    if expr[0] in ("and", "or"):
        return [r for e in expr[1] for r in refs(e)]
    return []


def short(text, n=46):
    return text if len(text) <= n else text[:n - 1] + "..."


def build():
    onto = Ontology(OWL)
    rules = {n: c for n, c in onto.classes.items() if c.expr is not None}
    summary = {n for n, c in rules.items() if c.category == "summary"}
    base = [n for n in rules if n not in summary]

    deps = {n: set() for n in rules}                  # classes that must sit to the left of n
    sub_edges, use_edges = [], []
    for n in base:
        for p in rules[n].parents:
            if p in rules:
                deps[n].add(p)
                sub_edges.append((p, n))
        for r in set(refs(rules[n].expr)):
            if r in rules and r not in rules[n].parents:
                deps[n].add(r)
                use_edges.append((r, n))
    for n in summary:
        for p in rules[n].parents:
            if p in rules:
                sub_edges.append((p, n))
        # summary classes are defined from many findings; drawing all those lines makes the picture unreadable

    level = {}

    def lvl(n):
        if n not in level:
            level[n] = 1 + max([lvl(d) for d in deps[n]], default=0)
        return level[n]

    for n in base:
        lvl(n)
    top = max(level.values(), default=1) + 1
    for n in summary:
        level[n] = top

    cols = {}
    for n, l in level.items():
        cols.setdefault(l, []).append(n)
    pos = {}
    for l, names in cols.items():
        names.sort(key=lambda n: (CAT_ORDER.index(rules[n].category) if rules[n].category in CAT_ORDER else 99,
                                  rules[n].label))
        for i, n in enumerate(names):
            pos[n] = (40 + l * (BOX_W + X_GAP), 70 + i * (BOX_H + Y_GAP))
    height = 70 + max(len(v) for v in cols.values()) * (BOX_H + Y_GAP) + 60
    width = 40 + (top + 1) * (BOX_W + X_GAP) + 20
    pos["Patient"] = (40, height / 2 - BOX_H / 2)

    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}" font-family="Segoe UI, Arial, sans-serif">',
           '<defs>'
           '<marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
           '<path d="M0,0 L10,5 L0,10 z" fill="#555"/></marker>'
           '<marker id="b" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
           '<path d="M0,0 L10,5 L0,10 z" fill="#8a6bbf"/></marker></defs>',
           f'<rect width="{width}" height="{height}" fill="white"/>',
           f'<text x="40" y="30" font-size="20" font-weight="bold">Heart Risk Ontology: classes and how they connect</text>',
           f'<text x="40" y="52" font-size="12" fill="#555">Solid = subclass. Dashed purple = defined using. '
           f'Colour = severity (grey info, yellow moderate, orange high, red urgent). '
           f'Right column = summary classes (each is a union of the serious findings; lines omitted).</text>']

    def edge(a, b, dashed):
        x1, y1 = pos[a][0] + BOX_W, pos[a][1] + BOX_H / 2
        x2, y2 = pos[b][0], pos[b][1] + BOX_H / 2
        mid = (x1 + x2) / 2
        style = ('stroke="#8a6bbf" stroke-dasharray="6,4" marker-end="url(#b)"' if dashed
                 else 'stroke="#555" marker-end="url(#a)"')
        svg.append(f'<path d="M{x1},{y1} C{mid},{y1} {mid},{y2} {x2},{y2}" fill="none" '
                   f'stroke-width="1.4" opacity="0.8" {style}/>')

    for n in base:                                   # Patient -> first-level base classes
        if level[n] == 1:
            x1, y1 = pos["Patient"][0] + 120, pos["Patient"][1] + BOX_H / 2
            x2, y2 = pos[n][0], pos[n][1] + BOX_H / 2
            mid = (x1 + x2) / 2
            svg.append(f'<path d="M{x1},{y1} C{mid},{y1} {mid},{y2} {x2},{y2}" fill="none" stroke="#bbb" '
                       f'stroke-width="1" opacity="0.7"/>')
    for a, b in use_edges:
        edge(a, b, True)
    for a, b in sub_edges:
        edge(a, b, False)

    px, py = pos["Patient"]
    svg.append(f'<rect x="{px}" y="{py}" width="120" height="{BOX_H}" rx="8" fill="#3b6ea5"/>'
               f'<text x="{px + 60}" y="{py + 22}" font-size="14" fill="white" text-anchor="middle" '
               f'font-weight="bold">Patient</text>')
    for n, (x, y) in pos.items():
        if n == "Patient":
            continue
        c = rules[n]
        svg.append(f'<rect x="{x}" y="{y}" width="{BOX_W}" height="{BOX_H}" rx="8" fill="{COLORS.get(c.severity, "#eee")}" '
                   f'stroke="#444" stroke-width="1"><title>{c.name}: {c.explanation}</title></rect>'
                   f'<text x="{x + 10}" y="{y + 22}" font-size="12">{short(c.label).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")}</text>')
    svg.append("</svg>")
    return "\n".join(svg), len(rules), len(sub_edges), len(use_edges)


def main():
    svg, n, s, u = build()
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("<!doctype html><html><head><meta charset='utf-8'><title>Heart Risk Ontology Graph</title>"
                "</head><body style='margin:0;background:#fff'>" + svg + "</body></html>")
    print(f"Created {OUT}")
    print(f"  {n} classes, {s} subclass links, {u} 'defined using' links")
    print("Open ontology_graph.html in your browser.")
    if sys.platform.startswith("win"):
        os.startfile(OUT)


if __name__ == "__main__":
    main()
