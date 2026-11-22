# Heart-Risk Ontology Chatbot

A chatbot that explains cardiovascular risk factors from lab values using an **OWL ontology** as its only knowledge source.
**No LLM, no cloud, no API keys.** Every answer comes from rules, explanations and citations stored in the ontology, so the bot cannot hallucinate.

> Educational project (KRL course). **Not a medical device and not clinically validated.** It does not diagnose and does not replace a doctor.

![demo screenshot](docs/protege_inferred_types.png)

## What it does

Type your values in plain text:

```
You: My LDL is 175, HDL 38, BP 150/95, fasting glucose 132, age 58 male, I am a smoker
```

and the bot answers with the values it understood, every finding it matched, why it matters, the guideline source, and what was *not* checked:

```
Values I used: Age: 58 years; Sex: male; LDL cholesterol: 175 mg/dL; ...

[HIGH] High LDL cholesterol (>= 160 mg/dL)
    Your values: LDL cholesterol: 175 mg/dL
    Why it matters: LDL of 160-189 mg/dL is classed as high.
    Source: NCEP ATP III
...
Overall: Worth reviewing with a clinician.
Not provided (so not checked): Total cholesterol, Triglycerides, HbA1c, BMI, ...
```

It also answers concept questions ("what is a normal HDL for women?"), explains its reasoning ("why am I flagged?"), gives next steps ("what should I do?"), reads mmol/L as well as mg/dL, and says honestly when a question is outside the ontology instead of guessing.

## How it works

```
user text / lab report
   -> extractor.py        reads values (lab names come from the ontology's synonyms)
   -> ontology_engine.py  loads heart_risk.owl and classifies the patient with its class definitions
   -> chatbot.py          builds the answer from hasExplanation / hasAdvice / hasSource annotations
```

The ontology (`heart_risk.owl`) contains:

| Part | Count / description |
|---|---|
| Data properties | 14 (age, sex, LDL, HDL, total cholesterol, triglycerides, systolic/diastolic BP, fasting glucose, HbA1c, BMI, smoker, family history, chest pain) |
| Defined rule classes | 24, e.g. `HighLDLPatient ≡ Patient and hasLDL some decimal[>= 160]` |
| Class hierarchy | e.g. `VeryHighLDL ⊂ HighLDL ⊂ BorderlineHighLDL`; combined and summary classes |
| Topics | 14 concepts the user can ask about, with synonyms |
| Annotations | `hasSource`, `hasExplanation`, `hasAdvice`, `hasSeverity`, `hasSynonym` |
| Sample patients | 3, for demonstrating reasoning in Protégé |

### Design decisions

- **Ontology owns the knowledge.** `rules.py` only generates the `.owl` file; the chatbot reads the `.owl` alone. Edit the ontology and the chatbot changes.
- **Print what the model sees.** Every reply starts with the values it extracted and ends with what was missing, so a misread value is visible.
- **Safety first, never sticky.** Chest pain is checked on every message and shown first; it applies to that message plus one follow-up, then disappears unless mentioned again.
- **Open-world behaviour.** A missing value never triggers a rule (HDL with unknown sex is not called low).
- **Honest fallback.** Out-of-scope questions get "that is not something my ontology covers" and a list of known topics.

## Run it

Requires Python 3.9+ and nothing else (standard library only).

```bash
python chatbot.py                      # chat in the terminal
python -m unittest -v test_chatbot     # 24 tests
python build_ontology.py               # regenerate heart_risk.owl after editing rules.py
python graph_ontology.py               # draw the ontology graph -> ontology_graph.html
```

On Windows use `py` instead of `python` if `python` is not recognised.

To use it from your own UI (Streamlit, Gradio, Flask):

```python
from chatbot import HeartRiskBot
bot = HeartRiskBot()
print(bot.handle("My LDL is 175, BP 150/95, age 58 male"))
```

## Verify the reasoning in Protégé

1. Open `heart_risk.owl` in [Protégé](https://protege.stanford.edu/).
2. *Reasoner > HermiT > Start reasoner*.
3. *Individuals* tab, select `SamplePatient_Ahmed`: the **inferred types** (High LDL, Stage 2 hypertension, Smoker ...) are derived by the reasoner from the class definitions. `SamplePatient_Sara` gets none.
4. *DL Query* tab, e.g. `'Current smoker' and 'High LDL cholesterol (>= 160 mg/dL)'` returns the matching patients.

## Add or change a rule

Edit `rules.py`, add a dict to `CLASSES`, run `python build_ontology.py`:

```python
dict(name="VeryHighLDLPatient", label="Very high LDL cholesterol (>= 190 mg/dL)",
     category="lipids", severity="high", parents=["HighLDLPatient"],
     expr=AND(PATIENT, num("hasLDL", ">=", 190)),
     explanation="...", advice="...", source="NCEP ATP III", synonyms=["very high ldl"])
```

## Limitations

- Educational only. Not validated on patients; not a medical device.
- It compares values with published cut-offs (NCEP ATP III, ACC/AHA, ADA, WHO). It does **not** compute a 10-year risk percentage and does not diagnose.
- Rules use single readings; a real diagnosis needs repeat measurements. Glucose rules assume a fasting sample.
- Source annotations name the guideline but not the section. Check the thresholds against the official documents before relying on them.
- Question understanding is keyword and synonym matching, not free-form language understanding.
- Classification inside the chatbot is done by a small purpose-built evaluator (standard library). Protégé with HermiT is used to verify the same results independently.

## Background

This project is the ontology-based successor of a RAG chatbot (FAISS + local Llama through Ollama). Replacing the LLM with an ontology removed hallucinated refusals and made every answer traceable to a rule and a source.

## License

MIT, see [LICENSE](LICENSE).
