"""Heart-risk chatbot whose only knowledge source is the OWL ontology (no LLM, no Ollama, no FAISS).

    python chatbot.py

From your own UI (Streamlit, Gradio, Flask ...):

    from chatbot import HeartRiskBot
    bot = HeartRiskBot()
    reply = bot.handle("My LDL is 175, BP 150/95, age 58 male, smoker")
"""
import json
import os
import re
import sys

from extractor import extract
from ontology_engine import Ontology, SEV_ORDER

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OWL = os.path.join(HERE, "heart_risk.owl")

DISCLAIMER = ("This is an educational tool built for a course. It is not a medical device, is not clinically "
              "validated, and does not replace a doctor.")

ADVICE_KW = ["what should i do", "what do i do", "advice", "next step", "recommend", "suggest", "kya karun",
             "kya karna", "what now", "see a doctor", "treatment", "what can i do"]
WHY_KW = ["why", "kyun", "kiyun", "explain my", "how did you", "reason", "because", "how come"]
SUMMARY_KW = ["risk", "assess", "summary", "summar", "result", "report", "status", "how am i", "my health",
              "check my", "analy", "kaisa", "kaise", "my values", "am i ok", "am i okay"]
HELP_KW = ["help", "what can you do", "commands", "how do i use", "how to use"]
TAG = {"urgent": "URGENT", "high": "HIGH", "moderate": "MODERATE", "info": "INFO"}


class HeartRiskBot:
    def __init__(self, owl_path=DEFAULT_OWL):
        if not os.path.exists(owl_path):
            import build_ontology
            build_ontology.main()
        self.onto = Ontology(owl_path)
        self.patient = {}      # values kept for the session
        self._carry = {}       # symptoms from the previous message (kept for ONE follow-up turn only)

    # ------------------------------------------------------------------ public API
    def banner(self):
        n_rules = sum(1 for c in self.onto.classes.values() if c.expr is not None and c.category != "summary")
        n_topics = sum(1 for c in self.onto.classes.values() if c.is_topic)
        return (f"Heart-risk chatbot (ontology-based). Loaded: {len(self.onto.properties)} properties, "
                f"{n_rules} rules, {n_topics} topics from {os.path.basename(self.onto.path)}.\n"
                "Type 'help' for examples, 'quit' to exit.\n" + DISCLAIMER)

    def handle(self, text):
        text = (text or "").strip()
        if not text:
            return "Please type a question or your lab values (for example: LDL 175, BP 150/95, age 58 male)."
        lt = text.lower()

        # ---- commands
        if lt in ("reset", "clear", "new patient", "start over"):
            self.patient, self._carry = {}, {}
            return "Cleared. I have no patient values now."
        if lt in ("values", "show values", "my values"):
            return self._values_line() or "I have no values yet."
        if lt.startswith("load "):
            return self._load_file(text[5:].strip().strip('"'))
        if lt in ("hi", "hello", "hey", "salam", "assalam o alaikum", "aoa") or any(k == lt for k in HELP_KW) \
                or lt.startswith("help"):
            return self._help()

        # ---- read what the user gave us
        ex = extract(text, self.onto)
        self.patient.update(ex.values)

        intent = self._intent(lt, ex.has_data)
        transient = dict(ex.transient)
        if not transient and self._carry and intent in ("advice", "why", "summary"):
            transient = dict(self._carry)          # bounded stickiness: one follow-up turn only
        self._carry = dict(ex.transient)           # next turn inherits only what THIS message said
        eval_patient = {**self.patient, **transient}

        notes = ex.notes + ex.rejected
        note_block = ("\n" + "\n".join(f"Note: {n}" for n in notes)) if notes else ""

        # ---- chest pain only, nothing else known: keep the emergency message short
        if transient and not self.patient:
            return self._urgent_block(eval_patient) + (
                "\n\nIf you are safe and have been medically assessed, you can share your lab values "
                "and I will go through them.")

        if intent == "assessment":
            return self._assessment(eval_patient, detail=any(k in lt for k in WHY_KW)) + note_block
        if intent == "advice":
            return self._advice(eval_patient)
        if intent == "why":
            return self._why(eval_patient, lt)
        if intent == "concept":
            return self._concept(lt, eval_patient)
        if intent == "summary":
            return self._assessment(eval_patient)
        return self._fallback(lt)

    # ------------------------------------------------------------------ intent
    def _intent(self, lt, has_data):
        if has_data:
            return "assessment"
        has_patient = bool(self.patient)
        if any(k in lt for k in ADVICE_KW):
            return "advice"
        if any(k in lt for k in WHY_KW) and has_patient:
            return "why"
        if self.onto.search(lt):
            return "concept"
        if any(k in lt for k in SUMMARY_KW):
            return "summary"
        return "fallback"

    # ------------------------------------------------------------------ answers
    def _values_line(self):
        if not self.patient:
            return ""
        order = list(self.onto.properties)
        parts = [self.onto.fmt_prop(p, self.patient[p]) for p in order if p in self.patient]
        return "Values I am using: " + "; ".join(parts)

    def _finding_block(self, name, patient, detail=False):
        c = self.onto.classes[name]
        vals = "; ".join(self.onto.fmt_prop(p, patient[p]) for p in self.onto.props_in(c.expr) if p in patient)
        lines = [f"[{TAG[c.severity]}] {c.label}"]
        if vals:
            lines.append(f"    Your values: {vals}")
        lines.append(f"    Why it matters: {c.explanation}")
        if detail:
            lines.append(f"    Rule in the ontology: {self.onto.describe(c.expr)}")
        lines.append(f"    Source: {c.source}")
        return "\n".join(lines)

    def _urgent_block(self, patient):
        items, _ = self.onto.findings(patient)
        urgent = [n for n in items if self.onto.classes[n].severity == "urgent"]
        out = ["!!! URGENT !!!"]
        for n in urgent:
            c = self.onto.classes[n]
            out += [c.label, c.explanation, f"What to do: {c.advice}", f"Source: {c.source}", ""]
        return "\n".join(out).rstrip()

    def _assessment(self, patient, detail=False):
        if not patient:
            return ("I have no values yet. Give me some, for example: "
                    "'LDL 175, HDL 38, BP 150/95, fasting glucose 132, age 58 male, smoker'.")
        items, summary = self.onto.findings(patient)
        out = []
        if any(self.onto.classes[n].severity == "urgent" for n in items):
            out += [self._urgent_block(patient), ""]
        out.append(self._values_line_for(patient))
        out.append("")
        regular = [n for n in items if self.onto.classes[n].severity != "urgent"]
        singles = [n for n in regular if self.onto.classes[n].category != "combined"]
        combined = [n for n in regular if self.onto.classes[n].category == "combined"]
        if singles:
            out.append("Findings (most specific first, worst first):")
            out += [self._finding_block(n, patient, detail) + "\n" for n in singles]
        if combined:
            out.append("Combined factors:")
            out += [self._finding_block(n, patient, detail) + "\n" for n in combined]
        if not items:
            out.append("None of the rules in my ontology was triggered by these values. That does not mean "
                       "you are risk-free: I only checked what you gave me.\n")
        out.append(self._overall(items, summary))
        missing = [p.label for n, p in self.onto.properties.items()
                   if n not in patient and n != "hasChestPain"]
        if missing:
            out.append("Not provided (so not checked): " + ", ".join(missing) + ".")
        out.append(DISCLAIMER)
        return "\n".join(out)

    def _values_line_for(self, patient):
        parts = [self.onto.fmt_prop(p, patient[p]) for p in self.onto.properties if p in patient]
        return "Values I used: " + "; ".join(parts)

    def _overall(self, items, summary):
        if "UrgentAttentionPatient" in summary:
            c = self.onto.classes["UrgentAttentionPatient"]
            return f"Overall: {c.label}. {c.advice}"
        if "ClinicianReviewPatient" in summary:
            c = self.onto.classes["ClinicianReviewPatient"]
            return f"Overall: {c.label}. {c.advice}"
        if items:
            return "Overall: some risk factors were found; none is in the range that needs urgent follow-up. Keep monitoring them."
        return "Overall: no risk factor triggered."

    def _advice(self, patient):
        items, _ = self.onto.findings(patient)
        if not items:
            return ("I have no findings to give advice on yet. Share your lab values first "
                    "(for example: LDL 175, BP 150/95, age 58 male).")
        out = ["Suggested next steps from the ontology (highest priority first):"]
        seen = set()
        for n in items:
            c = self.onto.classes[n]
            if c.advice in seen:
                continue
            seen.add(c.advice)
            out.append(f"- [{TAG[c.severity]}] {c.label}: {c.advice}  (Source: {c.source})")
        out.append(DISCLAIMER)
        return "\n".join(out)

    def _why(self, patient, lt):
        items, _ = self.onto.findings(patient)
        if not items:
            return "No rule was triggered by your values, so there is nothing to explain."
        hits = [h for h in self.onto.search(lt) if h in items]
        chosen = hits or items
        out = ["Here is the reasoning, from your values to the rule that fired:"]
        out += [self._finding_block(n, patient, detail=True) + "\n" for n in chosen]
        return "\n".join(out).rstrip()

    def _concept(self, lt, patient):
        hits = self.onto.search(lt)[:3]
        out = []
        for name in hits:
            c = self.onto.classes[name]
            if c.is_topic:
                out.append(self._topic_text(c, patient))
            else:
                out.append(self._class_text(c, patient))
        out.append(DISCLAIMER)
        return "\n\n".join(out)

    def _topic_text(self, c, patient):
        lines = [f"{c.label}", c.explanation]
        rules = []
        for n, k in self.onto.classes.items():
            if k.expr is None or k.category in ("summary", "combined"):
                continue
            if any(self.onto.uses_property_directly(k.expr, p) for p in c.relates):
                rules.append(f"  - [{TAG[k.severity]}] {self.onto.describe(k.expr)}")
        if rules:
            lines.append("Rules in my ontology:")
            lines += rules
        have = [self.onto.fmt_prop(p, patient[p]) for p in c.relates if p in patient]
        if have:
            lines.append("Your value: " + "; ".join(have))
        lines.append(f"Source: {c.source}")
        return "\n".join(lines)

    def _class_text(self, c, patient):
        lines = [c.label, c.explanation, f"Rule in the ontology: {self.onto.describe(c.expr)}"]
        needed = self.onto.props_in(c.expr)
        if all(p in patient for p in needed) or any(p in patient for p in needed):
            applies = c.name in self.onto.classify(patient)
            known = "; ".join(self.onto.fmt_prop(p, patient[p]) for p in needed if p in patient)
            lines.append(f"With your values ({known}) this {'applies' if applies else 'does not apply'}"
                         + ("" if all(p in patient for p in needed) else " (some inputs are missing, so I cannot be sure)") + ".")
        else:
            lines.append("Give me the relevant values and I will check whether it applies to you.")
        lines.append(f"What to do: {c.advice}")
        lines.append(f"Source: {c.source}")
        return "\n".join(lines)

    def _fallback(self, lt):
        topics = [c.label for c in self.onto.classes.values() if c.is_topic]
        return ("That is not something my ontology covers, so I will not guess.\n"
                "I can: assess lab values (LDL, HDL, total cholesterol, triglycerides, blood pressure, glucose, "
                "HbA1c, BMI, age, sex, smoking, family history, chest pain), explain why a finding fired, "
                "and give next steps.\n"
                "Topics I know: " + ", ".join(topics) + ".\n"
                "If you think this should be covered, tell me the exact term; it can be added to the ontology as a synonym.")

    def _help(self):
        return ("You can type things like:\n"
                "  My LDL is 175, HDL 38, BP 150/95, fasting glucose 132, age 58 male, smoker\n"
                "  What is a normal HDL for women?\n"
                "  Why am I flagged?   /   What should I do?\n"
                "  load report.txt   (reads a lab report text or .json file)\n"
                "  values   /   reset   /   quit\n"
                "Units are mg/dL by default; mmol/L values are detected and converted.\n"
                + DISCLAIMER)

    def _load_file(self, path):
        if not os.path.isfile(path):
            return f"I could not find the file '{path}'."
        try:
            with open(path, encoding="utf-8") as f:
                raw = f.read()
            if path.lower().endswith(".json"):
                data = json.loads(raw)
                raw = "\n".join(f"{k}: {v}" for k, v in data.items())
        except Exception as e:
            return f"I could not read '{path}': {e}"
        return self.handle(raw)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    bot = HeartRiskBot()
    print(bot.banner())
    while True:
        try:
            msg = input("\nYou: ")
        except (EOFError, KeyboardInterrupt):
            break
        if msg.strip().lower() in ("quit", "exit", "q"):
            break
        print("\nBot:", bot.handle(msg))


if __name__ == "__main__":
    main()
