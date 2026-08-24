"""Build a compact index of the generated Synthea FHIR cohort.

Reads data/synthea/fhir/*.json (Synthea R4 patient bundles) and writes
data/patient_index.json with, per patient: id, name, gender, birthDate, MRN,
condition texts, medication texts, and recent lab observations (code + date +
value). This lets benchmark cases reference real generated records instead of
inventing patient data.

Run from the repo root:
    python scripts/build_patient_index.py
"""
from __future__ import annotations

import glob
import json
import os

FHIR_DIR = os.path.join("data", "synthea", "fhir")
OUT = os.path.join("data", "patient_index.json")


def _name(patient: dict) -> str:
    nm = (patient.get("name") or [{}])[0]
    given = " ".join(nm.get("given", []))
    return f"{given} {nm.get('family', '')}".strip()


def _mrn(patient: dict) -> str | None:
    for ident in patient.get("identifier", []):
        text = (ident.get("type") or {}).get("text", "")
        if text == "Medical Record Number":
            return ident.get("value")
    return None


def _obs(resource: dict) -> dict | None:
    code = (resource.get("code") or {}).get("text")
    date = resource.get("effectiveDateTime")
    value = None
    if "valueQuantity" in resource:
        vq = resource["valueQuantity"]
        value = f"{vq.get('value')} {vq.get('unit', '')}".strip()
    if not code:
        return None
    return {"code": code, "date": date, "value": value}


def main() -> None:
    index = []
    for path in sorted(glob.glob(os.path.join(FHIR_DIR, "*.json"))):
        bundle = json.load(open(path, encoding="utf-8"))
        patient = None
        conditions, medications, observations = [], [], []
        for entry in bundle.get("entry", []):
            r = entry.get("resource", {})
            rt = r.get("resourceType")
            if rt == "Patient":
                patient = r
            elif rt == "Condition":
                t = (r.get("code") or {}).get("text")
                if t:
                    conditions.append(t)
            elif rt == "MedicationRequest":
                t = (r.get("medicationCodeableConcept") or {}).get("text")
                if t:
                    medications.append(t)
            elif rt == "Observation":
                o = _obs(r)
                if o:
                    observations.append(o)
        if patient is None:
            continue
        observations.sort(key=lambda o: o.get("date") or "", reverse=True)
        index.append(
            {
                "id": patient.get("id"),
                "mrn": _mrn(patient),
                "name": _name(patient),
                "gender": patient.get("gender"),
                "birthDate": patient.get("birthDate"),
                "source_file": os.path.basename(path),
                "n_conditions": len(conditions),
                "n_medications": len(medications),
                "conditions": sorted(set(conditions))[:40],
                "medications": sorted(set(medications))[:40],
                "recent_observations": observations[:25],
            }
        )
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(index, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"Wrote {OUT} with {len(index)} patients")


if __name__ == "__main__":
    main()
