"""Generate heart_risk.owl (OWL 2, RDF/XML) from rules.py.

Open the result in Protege: Reasoner > HermiT > Start reasoner. The three sample
patients get classified under the defined classes (Inferred types).

Run:  python build_ontology.py
"""
import os
from xml.sax.saxutils import escape

import rules

XSD = "http://www.w3.org/2001/XMLSchema#"
BASE = "http://example.org/heart-risk"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "heart_risk.owl")

FACETS = {">=": "minInclusive", ">": "minExclusive", "<=": "maxInclusive", "<": "maxExclusive"}
ANNOTATIONS = ["hasSource", "hasExplanation", "hasAdvice", "hasSeverity", "hasCategory",
               "hasSynonym", "hasUnit", "hasMin", "hasMax", "hasMmolFactor", "hasMmolBelow", "relatesTo"]


def fmt(v):
    return format(v, "g") if isinstance(v, float) else str(v)


def literal(value, datatype):
    if datatype == "boolean":
        return f'rdf:datatype="{XSD}boolean">{"true" if value else "false"}'
    if datatype == "integer":
        return f'rdf:datatype="{XSD}integer">{int(value)}'
    if datatype == "decimal":
        return f'rdf:datatype="{XSD}decimal">{fmt(value)}'
    return f'rdf:datatype="{XSD}string">{escape(str(value))}'


def render(expr):
    kind = expr[0]
    if kind == "ref":
        return f'<owl:Class rdf:about="#{expr[1]}"/>'
    if kind in ("and", "or"):
        tag = "intersectionOf" if kind == "and" else "unionOf"
        inner = "\n".join(render(e) for e in expr[1])
        return f'<owl:Class><owl:{tag} rdf:parseType="Collection">\n{inner}\n</owl:{tag}></owl:Class>'
    if kind == "val":
        prop, value = expr[1], expr[2]
        dt = rules.PROPERTIES[prop]["datatype"]
        return (f'<owl:Restriction><owl:onProperty rdf:resource="#{prop}"/>'
                f'<owl:hasValue {literal(value, dt)}</owl:hasValue></owl:Restriction>')
    if kind == "num":
        prop = expr[1]
        dt = rules.PROPERTIES[prop]["datatype"]
        facets = "".join(
            f'<rdf:Description><xsd:{FACETS[op]} rdf:datatype="{XSD}{dt}">{fmt(v)}</xsd:{FACETS[op]}></rdf:Description>'
            for op, v in expr[2])
        return (f'<owl:Restriction><owl:onProperty rdf:resource="#{prop}"/><owl:someValuesFrom>'
                f'<rdfs:Datatype><owl:onDatatype rdf:resource="{XSD}{dt}"/>'
                f'<owl:withRestrictions rdf:parseType="Collection">{facets}</owl:withRestrictions>'
                f'</rdfs:Datatype></owl:someValuesFrom></owl:Restriction>')
    raise ValueError(f"unknown expression {expr!r}")


def ann(tag, text):
    return f"    <{tag}>{escape(str(text))}</{tag}>\n"


def build():
    o = []
    o.append('<?xml version="1.0" encoding="UTF-8"?>\n')
    o.append(f'<rdf:RDF xmlns="{BASE}#" xml:base="{BASE}"\n'
             '     xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"\n'
             '     xmlns:owl="http://www.w3.org/2002/07/owl#"\n'
             f'     xmlns:xsd="{XSD}"\n'
             '     xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#">\n')
    o.append(f'  <owl:Ontology rdf:about="{BASE}">\n'
             '    <rdfs:label>Heart Risk Ontology</rdfs:label>\n'
             '    <rdfs:comment>Educational ontology of cardiovascular risk factors and published cut-offs. '
             'Not a medical device and not clinically validated.</rdfs:comment>\n'
             '  </owl:Ontology>\n\n')

    for a in ANNOTATIONS:
        o.append(f'  <owl:AnnotationProperty rdf:about="#{a}"/>\n')

    o.append('\n  <owl:Class rdf:about="#Patient"><rdfs:label>Patient</rdfs:label></owl:Class>\n')
    o.append('  <owl:Class rdf:about="#Concept"><rdfs:label>Concept</rdfs:label></owl:Class>\n\n')

    # data properties
    for name, p in rules.PROPERTIES.items():
        o.append(f'  <owl:DatatypeProperty rdf:about="#{name}">\n'
                 '    <rdf:type rdf:resource="http://www.w3.org/2002/07/owl#FunctionalProperty"/>\n'
                 '    <rdfs:domain rdf:resource="#Patient"/>\n'
                 f'    <rdfs:range rdf:resource="{XSD}{p["datatype"]}"/>\n')
        o.append(ann("rdfs:label", p["label"]))
        if p["unit"]:
            o.append(ann("hasUnit", p["unit"]))
        for key, tag in (("mn", "hasMin"), ("mx", "hasMax"),
                         ("mmol_factor", "hasMmolFactor"), ("mmol_below", "hasMmolBelow")):
            if key in p:
                o.append(ann(tag, p[key]))
        for s in p["synonyms"]:
            o.append(ann("hasSynonym", s))
        o.append("  </owl:DatatypeProperty>\n\n")

    # topics
    for t in rules.TOPICS:
        o.append(f'  <owl:Class rdf:about="#{t["name"]}">\n'
                 '    <rdfs:subClassOf rdf:resource="#Concept"/>\n')
        o.append(ann("rdfs:label", t["label"]))
        o.append(ann("hasExplanation", t["explanation"]))
        o.append(ann("hasSource", t["source"]))
        for p in t["props"]:
            o.append(ann("relatesTo", p))
        for s in t["synonyms"]:
            o.append(ann("hasSynonym", s))
        o.append("  </owl:Class>\n\n")

    # finding classes
    for c in rules.CLASSES:
        o.append(f'  <owl:Class rdf:about="#{c["name"]}">\n')
        o.append(ann("rdfs:label", c["label"]))
        for parent in c["parents"]:
            o.append(f'    <rdfs:subClassOf rdf:resource="#{parent}"/>\n')
        o.append(f'    <owl:equivalentClass>\n{render(c["expr"])}\n    </owl:equivalentClass>\n')
        o.append(ann("hasSeverity", c["severity"]))
        o.append(ann("hasCategory", c["category"]))
        o.append(ann("hasExplanation", c["explanation"]))
        o.append(ann("hasAdvice", c["advice"]))
        o.append(ann("hasSource", c["source"]))
        for s in c["synonyms"]:
            o.append(ann("hasSynonym", s))
        o.append("  </owl:Class>\n\n")

    # sample individuals
    for name, props in rules.INDIVIDUALS.items():
        o.append(f'  <owl:NamedIndividual rdf:about="#{name}">\n'
                 '    <rdf:type rdf:resource="#Patient"/>\n')
        for prop, value in props.items():
            dt = rules.PROPERTIES[prop]["datatype"]
            o.append(f'    <{prop} {literal(value, dt)}</{prop}>\n')
        o.append("  </owl:NamedIndividual>\n\n")

    o.append("</rdf:RDF>\n")
    return "".join(o)


def main():
    text = build()
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Wrote {OUT}")
    print(f"  data properties : {len(rules.PROPERTIES)}")
    print(f"  topics          : {len(rules.TOPICS)}")
    print(f"  finding classes : {len(rules.CLASSES)}")
    print(f"  sample patients : {len(rules.INDIVIDUALS)}")


if __name__ == "__main__":
    main()
