"""In-memory FHIR store over a Synthea R4 cohort.

Loads Synthea patient bundles once and answers simple, MedAgentBench-style
queries (Patient / Condition / Observation / MedicationRequest). Every read is
routed through :meth:`FhirStore.search`, so a caller (the environment) can
account for exactly which resource types an agent touched -- this is what makes
the least-privilege / data-exposure metric measurable.

Synthetic data only. No PHI.
"""
from __future__ import annotations

import datetime as _dt
import glob
import json
import os
from dataclasses import dataclass, field

RESOURCE_TYPES = ("Patient", "Condition", "Observation", "MedicationRequest")


def _days_between(iso_date: str | None, as_of: str) -> int | None:
    if not iso_date:
        return None
    try:
        d = _dt.date.fromisoformat(iso_date[:10])
        a = _dt.date.fromisoformat(as_of[:10])
    except ValueError:
        return None
    return (a - d).days


@dataclass
class Patient:
    id: str
    mrn: str | None
    name: str
    gender: str | None
    birth_date: str | None
    conditions: list[dict] = field(default_factory=list)       # {text}
    medications: list[dict] = field(default_factory=list)       # {text, note}
    observations: list[dict] = field(default_factory=list)      # {code, date, value, value_num}


class FhirStore:
    def __init__(self, fhir_dir: str = os.path.join("data", "synthea", "fhir")):
        self._patients: dict[str, Patient] = {}
        self._load(fhir_dir)

    # ---- loading -------------------------------------------------------
    def _load(self, fhir_dir: str) -> None:
        for path in sorted(glob.glob(os.path.join(fhir_dir, "*.json"))):
            bundle = json.load(open(path, encoding="utf-8"))
            p = self._parse_bundle(bundle)
            if p is not None:
                self._patients[p.id] = p

    @staticmethod
    def _parse_bundle(bundle: dict) -> Patient | None:
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
                    conditions.append({"text": t})
            elif rt == "MedicationRequest":
                t = (r.get("medicationCodeableConcept") or {}).get("text")
                if t:
                    medications.append({"text": t, "note": _first_note(r)})
            elif rt == "Observation":
                code = (r.get("code") or {}).get("text")
                if not code:
                    continue
                vq = r.get("valueQuantity") or {}
                observations.append(
                    {
                        "code": code,
                        "date": r.get("effectiveDateTime"),
                        "value": (
                            f"{vq.get('value')} {vq.get('unit', '')}".strip()
                            if "valueQuantity" in r
                            else None
                        ),
                        "value_num": vq.get("value") if "valueQuantity" in r else None,
                    }
                )
        if patient is None:
            return None
        nm = (patient.get("name") or [{}])[0]
        name = f"{' '.join(nm.get('given', []))} {nm.get('family', '')}".strip()
        mrn = None
        for ident in patient.get("identifier", []):
            if (ident.get("type") or {}).get("text") == "Medical Record Number":
                mrn = ident.get("value")
        observations.sort(key=lambda o: o.get("date") or "", reverse=True)
        return Patient(
            id=patient.get("id"),
            mrn=mrn,
            name=name,
            gender=patient.get("gender"),
            birth_date=patient.get("birthDate"),
            conditions=conditions,
            medications=medications,
            observations=observations,
        )

    # ---- access --------------------------------------------------------
    def patient_ids(self) -> list[str]:
        return list(self._patients)

    def get_patient(self, pid: str) -> Patient | None:
        return self._patients.get(pid)

    def find_by_name_dob(self, name: str, dob: str) -> Patient | None:
        for p in self._patients.values():
            if p.name.lower() == name.lower() and p.birth_date == dob:
                return p
        return None

    def search(self, pid: str, resource_type: str, code_substr: str | None = None) -> list[dict]:
        """Return simplified records of ``resource_type`` for a patient.

        This is the single read path; the environment wraps it to log accesses.
        """
        p = self._patients.get(pid)
        if p is None:
            return []
        if resource_type == "Patient":
            return [
                {
                    "id": p.id,
                    "mrn": p.mrn,
                    "name": p.name,
                    "gender": p.gender,
                    "birthDate": p.birth_date,
                }
            ]
        if resource_type == "Condition":
            return list(p.conditions)
        if resource_type == "MedicationRequest":
            return list(p.medications)
        if resource_type == "Observation":
            obs = p.observations
            if code_substr:
                s = code_substr.lower()
                obs = [o for o in obs if s in o["code"].lower()]
            return obs
        return []

    def latest_observation(
        self,
        pid: str,
        code_substr: str,
        within_days: int,
        as_of: str,
        numeric_only: bool = False,
    ) -> dict | None:
        """Most recent Observation matching ``code_substr`` within a window.

        With ``numeric_only`` the most recent reading that actually carries a
        numeric value is returned, so a value-less panel header does not mask a
        real screening score (this bit the PHQ-9 escalation check in v0).
        """
        for o in self.search(pid, "Observation", code_substr):
            age = _days_between(o.get("date"), as_of)
            if age is None or not (0 <= age <= within_days):
                continue
            if numeric_only and o.get("value_num") is None:
                continue
            return o
        return None


def _first_note(resource: dict) -> str | None:
    notes = resource.get("note") or []
    if notes and isinstance(notes, list):
        return notes[0].get("text")
    return None
