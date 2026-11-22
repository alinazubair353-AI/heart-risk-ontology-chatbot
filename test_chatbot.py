"""Run:  python -m unittest -v test_chatbot"""
import os
import unittest
import xml.etree.ElementTree as ET

from chatbot import HeartRiskBot
from extractor import extract
from ontology_engine import Ontology

OWL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "heart_risk.owl")
ONTO = Ontology(OWL)


def shown(onto, patient):
    items, summary = onto.findings(patient)
    return set(items), set(summary)


class OntologyReasoning(unittest.TestCase):
    def test_sample_ahmed(self):
        items, summary = shown(ONTO, ONTO.individuals["SamplePatient_Ahmed"])
        expected = {"HighLDLPatient", "HighTotalCholesterolPatient", "LowHDLPatient", "HighTriglyceridePatient",
                    "Stage2HypertensionPatient", "DiabetesRangeFastingGlucosePatient", "ObesePatient",
                    "SmokerPatient", "AgeRiskFactorPatient", "HypertensionWithDiabetesRangePatient",
                    "SmokerWithAtherogenicLipidsPatient"}
        self.assertEqual(items, expected)                       # parents (Borderline..., Stage1...) are pruned
        self.assertIn("ClinicianReviewPatient", summary)
        self.assertNotIn("UrgentAttentionPatient", summary)

    def test_sample_sara_has_no_findings(self):
        items, summary = shown(ONTO, ONTO.individuals["SamplePatient_Sara"])
        self.assertEqual(items, set())
        self.assertEqual(summary, set())

    def test_sample_chest_pain_is_urgent(self):
        items, summary = shown(ONTO, ONTO.individuals["SamplePatient_ChestPain"])
        self.assertIn("ChestPainAlertPatient", items)
        self.assertIn("UrgentAttentionPatient", summary)

    def test_hdl_depends_on_sex(self):
        self.assertIn("LowHDLPatient", ONTO.classify({"hasSex": "female", "hasHDL": 45}))
        self.assertNotIn("LowHDLPatient", ONTO.classify({"hasSex": "male", "hasHDL": 45}))
        self.assertNotIn("LowHDLPatient", ONTO.classify({"hasHDL": 30}))   # sex unknown -> cannot conclude

    def test_boundaries(self):
        self.assertNotIn("HighLDLPatient", ONTO.classify({"hasLDL": 159}))
        self.assertIn("HighLDLPatient", ONTO.classify({"hasLDL": 160}))
        self.assertNotIn("HypertensiveCrisisRangePatient", ONTO.classify({"hasSystolicBP": 180, "hasDiastolicBP": 120}))
        self.assertIn("HypertensiveCrisisRangePatient", ONTO.classify({"hasSystolicBP": 181}))

    def test_every_rule_is_documented(self):
        for c in ONTO.classes.values():
            self.assertTrue(c.label and c.explanation and c.source, c.name)
            if c.expr is not None and c.category != "summary":
                self.assertTrue(c.advice and c.synonyms, c.name)

    def test_owl_is_well_formed(self):
        self.assertEqual(ET.parse(OWL).getroot().tag.split("}")[1], "RDF")


class Extraction(unittest.TestCase):
    def test_full_sentence(self):
        v = extract("My LDL is 175, HDL 38, BP 150/95, fasting glucose 132, age 58 male, smoker", ONTO).values
        self.assertEqual((v["hasLDL"], v["hasHDL"], v["hasSystolicBP"], v["hasDiastolicBP"]), (175, 38, 150, 95))
        self.assertEqual((v["hasFastingGlucose"], v["hasAge"], v["hasSex"]), (132, 58, "male"))
        self.assertIs(v.get("isSmoker"), None)    # "smoker" alone, without "I am", is not taken as a statement

    def test_first_person_smoker_and_negation(self):
        self.assertTrue(extract("I am a smoker", ONTO).values["isSmoker"])
        self.assertFalse(extract("I am a non-smoker", ONTO).values["isSmoker"])

    def test_labels_do_not_steal_each_other_numbers(self):
        v = extract("LDL is fine. HDL 45", ONTO).values
        self.assertNotIn("hasLDL", v)
        self.assertEqual(v["hasHDL"], 45)

    def test_ldl_cholesterol_not_read_as_total(self):
        v = extract("LDL cholesterol 120, total cholesterol 210", ONTO).values
        self.assertEqual((v["hasLDL"], v["hasTotalCholesterol"]), (120, 210))

    def test_mmol_is_converted(self):
        ex = extract("LDL 4.5 mmol/L", ONTO)
        self.assertAlmostEqual(ex.values["hasLDL"], 4.5 * 38.67, places=1)

    def test_implausible_value_rejected(self):
        ex = extract("LDL 5000", ONTO)
        self.assertNotIn("hasLDL", ex.values)
        self.assertTrue(ex.rejected)

    def test_date_is_not_blood_pressure(self):
        self.assertNotIn("hasSystolicBP", extract("report dated 12/05/2026", ONTO).values)

    def test_female_not_read_as_male(self):
        self.assertEqual(extract("55 year old female", ONTO).values["hasSex"], "female")


class Chatbot(unittest.TestCase):
    def setUp(self):
        self.bot = HeartRiskBot(OWL)

    def test_assessment_shows_values_rules_sources(self):
        r = self.bot.handle("My LDL is 175, HDL 38, BP 150/95, fasting glucose 132, age 58 male, smoker: yes")
        for text in ("High LDL cholesterol", "Stage 2 hypertension", "Source:", "Values I used", "Not provided"):
            self.assertIn(text, r)
        self.assertNotIn("Borderline-high LDL", r)    # parent class hidden
        self.assertIn("Worth reviewing with a clinician", r)

    def test_chest_pain_urgent_then_not_sticky(self):
        r1 = self.bot.handle("I have chest pain")
        self.assertIn("URGENT", r1)
        r2 = self.bot.handle("what is LDL")                 # unrelated question: no banner
        self.assertNotIn("URGENT", r2)
        r3 = self.bot.handle("my LDL is 120")               # new data: no banner
        self.assertNotIn("URGENT", r3)

    def test_chest_pain_followup_gets_one_turn(self):
        self.bot.handle("I have chest pain")
        r = self.bot.handle("what should I do")
        self.assertIn("emergency", r.lower())
        r = self.bot.handle("what should I do")             # second follow-up: gone
        self.assertNotIn("emergency", r.lower())

    def test_negated_chest_pain(self):
        r = self.bot.handle("no chest pain, my LDL is 120")
        self.assertNotIn("URGENT", r)

    def test_concept_question_is_answered_not_refused(self):
        r = self.bot.handle("what is a normal HDL for women?")
        self.assertIn("50", r)
        self.assertNotIn("not something my ontology covers", r)

    def test_unknown_topic_falls_back_honestly(self):
        r = self.bot.handle("what is the weather in Lahore")
        self.assertIn("not something my ontology covers", r)

    def test_advice_after_values(self):
        self.bot.handle("LDL 195, age 50 male")
        r = self.bot.handle("what should I do?")
        self.assertIn("treatment discussion", r)

    def test_why_gives_rule(self):
        self.bot.handle("LDL 175")
        r = self.bot.handle("why am I flagged?")
        self.assertIn("Rule in the ontology", r)
        self.assertIn(">= 160", r)

    def test_reset(self):
        self.bot.handle("LDL 175")
        self.bot.handle("reset")
        self.assertIn("no values", self.bot.handle("values").lower())


if __name__ == "__main__":
    unittest.main()
