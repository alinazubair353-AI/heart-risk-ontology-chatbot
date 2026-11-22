"""Turns free text or a lab-report text into patient values.

Numeric lab names come from the ontology (hasSynonym on each data property), so adding
a synonym in rules.py / the OWL file is enough. Yes/no flags and sex use a few regexes.
Everything extracted is echoed back to the user ("Values I used") so nothing is silent.
"""
import re
from dataclasses import dataclass, field

# words allowed between a lab name and its number: "LDL is 175", "LDL: 175", "LDL level of 175"
GAP = (r"[\s:=\-]*(?:(?:is|was|of|at|level|levels|value|reading|result|around|about|approx|hai|ha|hy|to|be)"
       r"[\s:=\-]*){0,3}")
NUMBER = r"(\d+(?:\.\d+)?)\s*(mg/dl|mmol/l)?"

SMOKER_NEG = [r"non[\s-]?smoker", r"not (?:a )?smok\w*", r"don'?t smoke", r"do not smoke", r"never smok\w*",
              r"no smoking", r"ex[\s-]?smoker", r"quit smoking", r"smok\w* nahi", r"smoke nahi", r"smoker\s*[:=]\s*(?:no|false|n)\b"]
SMOKER_POS = [r"\b(?:i|im|i'm|i am|main)\b[^.?!]{0,20}\b(?:smoke|smokes|smoker|smoking)\b",
              r"\bsmoker\s*[:=]\s*(?:yes|true|y)\b", r"\bcurrent smoker\b", r"\bmain\b[^.?!]{0,15}\bsmoke\b",
              r"\bi am a smoker\b", r"\bsmoke\s+(?:karta|karti)\b"]
FAMILY_NEG = [r"no family history", r"family history\s*[:=]\s*(?:no|false)", r"no history of heart"]
FAMILY_POS = [r"family history (?:of )?(?:heart|cardiac|cvd|premature|stroke)", r"family history\s*[:=]\s*(?:yes|true)",
              r"\b(?:father|mother|brother|sister|parent|parents)\b[^.?!]{0,40}\b(?:heart attack|heart disease|stroke|cardiac)\b"]
CHEST_NEG = [r"\b(?:no|not|without|never|nahi|denies|deny)\b\s+(?:any\s+)?chest\s*(?:pain|tightness|pressure|discomfort)",
             r"chest\s*(?:pain|tightness|pressure|discomfort)\s*(?:nahi|nhi)", r"chest\s*pain\s*[:=]\s*(?:no|false)"]
CHEST_POS = [r"chest\s*(?:pain|tightness|pressure|discomfort)", r"seene\s*(?:me|mein|mai)\s*(?:dard|bhari)"]


@dataclass
class Extraction:
    values: dict = field(default_factory=dict)     # stored for the session
    transient: dict = field(default_factory=dict)  # symptoms: evaluated now, never stored
    notes: list = field(default_factory=list)
    rejected: list = field(default_factory=list)

    @property
    def has_data(self):
        return bool(self.values or self.transient)


def _any(patterns, s):
    return any(re.search(p, s) for p in patterns)


def extract(text, onto):
    ex = Extraction()
    s = text.lower()
    props = onto.properties

    def store(prop, value, unit_given=None):
        p = props[prop]
        if p.mmol_factor and (unit_given == "mmol/l" or (unit_given is None and p.mmol_below and value < p.mmol_below)):
            converted = value * p.mmol_factor
            ex.notes.append(f"{p.label}: {value:g} looks like mmol/L, converted to {converted:.0f} {p.unit}.")
            value = converted
        if (p.mn is not None and value < p.mn) or (p.mx is not None and value > p.mx):
            ex.rejected.append(f"{p.label} = {value:g} is outside the plausible range "
                               f"({p.mn:g}-{p.mx:g} {p.unit}); I ignored it. Please check for a typo.")
            return
        ex.values[prop] = int(round(value)) if p.datatype == "integer" else value

    def mask(m):
        nonlocal s
        s = s[:m.start()] + " " * (m.end() - m.start()) + s[m.end():]

    # 1) blood pressure written as 150/95
    for m in re.finditer(r"(?<![\d/])(\d{2,3})\s*/\s*(\d{2,3})(?![\d/])", s):
        sys_, dia = float(m.group(1)), float(m.group(2))
        if 60 <= sys_ <= 300 and 30 <= dia <= 200 and sys_ > dia:
            ex.values["hasSystolicBP"], ex.values["hasDiastolicBP"] = sys_, dia
            mask(m)
            break

    # 2) "58 years old", "58 saal"
    m = re.search(r"(?<![\d.])(\d{1,3})\s*(?:years?|yrs?|yo|y/o|saal|sal)\b(?:\s*old)?", s)
    if m:
        store("hasAge", float(m.group(1)))
        mask(m)

    # 3) numeric labs, longest synonym first so "ldl cholesterol" is used before bare "cholesterol"
    cands = [(syn, pname) for pname, p in props.items() if p.datatype in ("decimal", "integer")
             for syn in p.synonyms]
    cands.sort(key=lambda x: -len(x[0]))
    done = set(ex.values)
    for syn, pname in cands:
        if pname in done:
            continue
        pat = r"(?<![a-z0-9])" + re.escape(syn) + r"(?![a-z0-9])" + GAP + NUMBER
        m = re.search(pat, s)
        if m:
            done.add(pname)
            store(pname, float(m.group(1)), m.group(2))
            mask(m)

    # 4) sex
    if re.search(r"(?<![a-z])(female|woman|girl|aurat|larki)(?![a-z])", s):
        ex.values["hasSex"] = "female"
    elif re.search(r"(?<![a-z])(male|man|boy|mard|larka)(?![a-z])", s):
        ex.values["hasSex"] = "male"

    # 5) yes/no flags (negations are checked first)
    if _any(SMOKER_NEG, s):
        ex.values["isSmoker"] = False
    elif _any(SMOKER_POS, s):
        ex.values["isSmoker"] = True
    if _any(FAMILY_NEG, s):
        ex.values["hasFamilyHistoryPrematureCVD"] = False
    elif _any(FAMILY_POS, s):
        ex.values["hasFamilyHistoryPrematureCVD"] = True
    if not _any(CHEST_NEG, s) and _any(CHEST_POS, s):
        ex.transient["hasChestPain"] = True

    if ex.values.get("hasAge", 99) < 18:
        ex.notes.append("This ontology covers adults (18+); results for a younger person are not meaningful.")
    if ex.values.get("hasFamilyHistoryPrematureCVD"):
        ex.notes.append("Family history counts only if the relative was young (father/brother under 55, mother/sister under 65).")
    return ex
