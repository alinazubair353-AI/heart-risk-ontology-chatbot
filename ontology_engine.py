"""Loads heart_risk.owl and answers questions from it.

No LLM and no external ontology library: the OWL file (RDF/XML) is parsed with the
standard library and the defined-class axioms (intersectionOf, unionOf, someValuesFrom
over a datatype restriction, hasValue) are evaluated directly against a patient.

This is a small purpose-built evaluator for the axiom shapes used in this project.
For the demo, Protege + HermiT gives the same classification on the sample patients.
"""
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

RDF = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
OWL = "{http://www.w3.org/2002/07/owl#}"
RDFS = "{http://www.w3.org/2000/01/rdf-schema#}"
H = "{http://example.org/heart-risk#}"

SEV_ORDER = {"info": 0, "moderate": 1, "high": 2, "urgent": 3}
OPS = {"minInclusive": ">=", "minExclusive": ">", "maxInclusive": "<=", "maxExclusive": "<"}


def _name(el):
    iri = el.get(RDF + "about") or el.get(RDF + "resource") or ""
    return iri.split("#")[-1]


def _literal(el):
    dt = el.get(RDF + "datatype", "")
    text = (el.text or "").strip()
    if dt.endswith("boolean"):
        return text.lower() == "true"
    if dt.endswith(("integer", "decimal", "double")):
        return float(text)
    return text


def num_fmt(x):
    return str(int(x)) if float(x) == int(x) else f"{x:g}"


@dataclass
class OClass:
    name: str
    label: str = ""
    expr: tuple = None
    parents: list = field(default_factory=list)
    severity: str = "info"
    category: str = ""
    explanation: str = ""
    advice: str = ""
    source: str = ""
    synonyms: list = field(default_factory=list)
    relates: list = field(default_factory=list)
    is_topic: bool = False


@dataclass
class OProperty:
    name: str
    label: str = ""
    datatype: str = "decimal"
    unit: str = ""
    synonyms: list = field(default_factory=list)
    mn: float = None
    mx: float = None
    mmol_factor: float = None
    mmol_below: float = None


class Ontology:
    def __init__(self, path):
        self.path = path
        self.classes = {}
        self.properties = {}
        self.individuals = {}
        self._load()

    # ------------------------------------------------------------------ loading
    def _load(self):
        root = ET.parse(self.path).getroot()
        for el in root.findall(OWL + "DatatypeProperty"):
            rng = el.find(RDFS + "range")
            p = OProperty(
                name=_name(el), label=el.findtext(RDFS + "label", ""),
                datatype=_name(rng) or "decimal" if rng is not None else "decimal",
                unit=el.findtext(H + "hasUnit", ""),
                synonyms=[s.text for s in el.findall(H + "hasSynonym")])
            for tag, attr in (("hasMin", "mn"), ("hasMax", "mx"),
                              ("hasMmolFactor", "mmol_factor"), ("hasMmolBelow", "mmol_below")):
                t = el.findtext(H + tag)
                if t is not None:
                    setattr(p, attr, float(t))
            self.properties[p.name] = p

        for el in root.findall(OWL + "Class"):
            name = _name(el)
            if name in ("Patient", "Concept"):
                continue
            parents = [_name(c) for c in el.findall(RDFS + "subClassOf")]
            c = OClass(
                name=name, label=el.findtext(RDFS + "label", name), parents=parents,
                severity=el.findtext(H + "hasSeverity", "info"),
                category=el.findtext(H + "hasCategory", ""),
                explanation=el.findtext(H + "hasExplanation", ""),
                advice=el.findtext(H + "hasAdvice", ""),
                source=el.findtext(H + "hasSource", ""),
                synonyms=[s.text.lower() for s in el.findall(H + "hasSynonym")],
                relates=[r.text for r in el.findall(H + "relatesTo")],
                is_topic="Concept" in parents)
            eq = el.find(OWL + "equivalentClass")
            if eq is not None:
                c.expr = self._parse(list(eq)[0])
            self.classes[name] = c

        for el in root.findall(OWL + "NamedIndividual"):
            values = {}
            for child in el:
                tag = child.tag.replace(H, "")
                if tag in self.properties:
                    values[tag] = _literal(child)
            self.individuals[_name(el)] = values

    def _parse(self, el):
        if el.tag == OWL + "Class":
            n = _name(el)
            if n:
                return ("ref", n)
            for kind, tag in (("and", "intersectionOf"), ("or", "unionOf")):
                c = el.find(OWL + tag)
                if c is not None:
                    return (kind, [self._parse(x) for x in c])
        if el.tag == OWL + "Restriction":
            prop = _name(el.find(OWL + "onProperty"))
            hv = el.find(OWL + "hasValue")
            if hv is not None:
                return ("val", prop, _literal(hv))
            dt = el.find(OWL + "someValuesFrom").find(RDFS + "Datatype")
            facets = []
            for d in dt.find(OWL + "withRestrictions"):
                for f in d:
                    facets.append((OPS[f.tag.split("}")[1]], float(f.text)))
            return ("num", prop, facets)
        raise ValueError(f"Unsupported axiom element: {el.tag}")

    # ------------------------------------------------------------------ reasoning
    @staticmethod
    def _cmp(v, op, x):
        return {">=": v >= x, ">": v > x, "<=": v <= x, "<": v < x}[op]

    def _holds(self, expr, patient, memo):
        k = expr[0]
        if k == "ref":
            return self._member(expr[1], patient, memo)
        if k == "and":
            return all(self._holds(e, patient, memo) for e in expr[1])
        if k == "or":
            return any(self._holds(e, patient, memo) for e in expr[1])
        if k == "val":
            v = patient.get(expr[1])
            if v is None:
                return False
            return str(v).lower() == expr[2].lower() if isinstance(expr[2], str) else v == expr[2]
        if k == "num":
            v = patient.get(expr[1])
            if v is None or isinstance(v, (bool, str)):
                return False
            return all(self._cmp(v, op, x) for op, x in expr[2])
        raise ValueError(k)

    def _member(self, name, patient, memo):
        if name == "Patient":
            return True
        if name not in memo:
            c = self.classes.get(name)
            memo[name] = bool(c and c.expr and self._holds(c.expr, patient, memo))
        return memo[name]

    def classify(self, patient):
        """All defined classes the patient belongs to."""
        memo = {}
        return [n for n, c in self.classes.items() if c.expr is not None and self._member(n, patient, memo)]

    def _ancestors(self, name):
        out, stack = set(), list(self.classes[name].parents)
        while stack:
            p = stack.pop()
            if p not in out and p in self.classes:
                out.add(p)
                stack.extend(self.classes[p].parents)
        return out

    def findings(self, patient):
        """(findings, summary): findings = most specific matches, worst first; summary = overall classes."""
        matched = self.classify(patient)
        summary = [n for n in matched if self.classes[n].category == "summary"]
        items = [n for n in matched if self.classes[n].category != "summary"]
        hidden = set()
        for n in items:
            hidden |= self._ancestors(n)
        items = [n for n in items if n not in hidden]
        items.sort(key=lambda n: (-SEV_ORDER.get(self.classes[n].severity, 0), self.classes[n].label))
        return items, summary

    # ------------------------------------------------------------------ introspection helpers
    def props_in(self, expr, seen=None):
        """Properties an expression depends on (follows class references)."""
        seen = set() if seen is None else seen
        out = []
        k = expr[0]
        if k in ("num", "val"):
            out.append(expr[1])
        elif k in ("and", "or"):
            for e in expr[1]:
                out += self.props_in(e, seen)
        elif k == "ref" and expr[1] in self.classes and expr[1] not in seen:
            seen.add(expr[1])
            c = self.classes[expr[1]]
            if c.expr:
                out += self.props_in(c.expr, seen)
        return list(dict.fromkeys(out))

    def uses_property_directly(self, expr, prop):
        k = expr[0]
        if k in ("num", "val"):
            return expr[1] == prop
        if k in ("and", "or"):
            return any(self.uses_property_directly(e, prop) for e in expr[1])
        return False

    def describe(self, expr, top=True):
        """Human-readable form of a class definition."""
        k = expr[0]
        if k == "ref":
            c = self.classes.get(expr[1])
            return c.label if c else expr[1]
        if k in ("and", "or"):
            parts = [self.describe(e, False) for e in expr[1] if not (e[0] == "ref" and e[1] == "Patient")]
            s = (" and " if k == "and" else " or ").join(parts)
            return s if top or len(parts) < 2 else f"({s})"
        p = self.properties[expr[1]]
        if k == "val":
            if isinstance(expr[2], bool):
                return p.label if expr[2] else f"not {p.label}"
            return f"{p.label} = {expr[2]}"
        unit = f" {p.unit}" if p.unit else ""
        return " and ".join(f"{p.label} {op} {num_fmt(x)}{unit}" for op, x in expr[2])

    def fmt_prop(self, prop, value):
        p = self.properties[prop]
        if isinstance(value, bool):
            return f"{p.label}: {'yes' if value else 'no'}"
        if isinstance(value, str):
            return f"{p.label}: {value}"
        unit = f" {p.unit}" if p.unit else ""
        return f"{p.label}: {num_fmt(value)}{unit}"

    # ------------------------------------------------------------------ question matching
    def search(self, text):
        """Match words in a question to topics and class synonyms. Longest term wins; matched text is masked."""
        t = " " + text.lower() + " "
        cands = []
        for c in self.classes.values():
            if c.category == "summary":
                continue
            for term in c.synonyms:
                cands.append((term, c.name))
        cands.sort(key=lambda x: -len(x[0]))
        hits = []
        for term, name in cands:
            pat = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])"
            if re.search(pat, t):
                t = re.sub(pat, lambda m: " " * len(m.group()), t)
                if name not in hits:
                    hits.append(name)
        return hits
