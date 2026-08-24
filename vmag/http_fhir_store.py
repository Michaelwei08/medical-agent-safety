"""A drop-in FhirStore that reads from a real FHIR server instead of disk.

WHY THIS IS A DROP-IN AND NOT A REWRITE
    The least-privilege / data-exposure metric does NOT live in the store. It
    lives in `Environment.read`, which appends a `ToolCall` recording the resource
    type, whether it was in scope, and whether it crossed patients - and then
    calls the store purely as a data source. The store surface the environment
    actually uses is two methods: `search` and `latest_observation`. So swapping
    the data source cannot weaken the metric, as long as the two methods return
    the same records.

    That is the whole design. `FhirStore` and `HttpFhirStore` are interchangeable
    from `Environment`'s point of view, which is what makes it meaningful to run
    the same evaluation against a real server and compare the numbers.

COHORT ISOLATION MATTERS AND IS PRESERVED
    `run_eval.py` deliberately builds TWO stores: the main cases run against
    `data/synthea/fhir` (seed 1) and the held-out cases against
    `data/synthea_s2/fhir` (seed 2), because the held-out cohort was generated
    after the policy was frozen. On one FHIR server both cohorts coexist, which
    would silently dissolve that separation.

    So this store takes a cohort allow-list. `from_dir` builds it by reading only
    the Patient ids out of the bundles in a directory - cheap, and it reproduces
    `FhirStore(that_dir)` exactly: a patient outside the cohort returns `[]`, the
    same as an unknown id does on disk.

RECORD SHAPES ARE COPIED FROM FhirStore._parse_bundle DELIBERATELY, INCLUDING ITS
FILTERS
    The disk parser drops a Condition or MedicationRequest whose `text` is empty,
    and an Observation with no `code.text`. Measured on one patient: the server
    holds 29 MedicationRequests where the disk store keeps 27, purely because of
    that filter. Equivalence requires reproducing it, not "fixing" it.

TIE ORDER IS THE ONE THING THAT CANNOT BE GUARANTEED
    Observations are sorted by date descending with a stable sort, so on disk a
    same-date tie keeps Synthea's bundle order. Over HTTP the input order is
    whatever the server returns, so ties may resolve differently. This does not
    change any policy outcome here: the only clause that reads a same-date tie is
    protocol item 3, and D044 established that clause is unfalsifiable on these
    cohorts because the numeric row always precedes the value-less one in bundle
    order (74/74). `verify_http_store.py` reports ordered and unordered agreement
    separately so the distinction stays visible rather than assumed away.
"""
from __future__ import annotations

import glob
import json
import os
import urllib.parse
import urllib.request

# 127.0.0.1, not localhost. On Windows `localhost` resolves to ::1 first and the
# IPv6 attempt costs a full timeout before falling back: measured 21.117s against
# 0.049s for the identical query returning identical bytes.
DEFAULT_BASE = "http://127.0.0.1:8080/fhir"
DEFAULT_TIMEOUT = 90
PAGE = 500          # large enough that the cohort's resources fit in one page

RESOURCE_TYPES = ("Patient", "Condition", "Observation", "MedicationRequest")


def _first_note(resource: dict) -> str | None:
    notes = resource.get("note") or []
    if notes and isinstance(notes, list):
        return notes[0].get("text")
    return None


def cohort_ids(fhir_dir: str) -> set[str]:
    """Patient ids in a bundle directory, without parsing the whole bundles."""
    out = set()
    for path in sorted(glob.glob(os.path.join(fhir_dir, "*.json"))):
        bundle = json.load(open(path, encoding="utf-8"))
        for entry in bundle.get("entry", []):
            r = entry.get("resource") or {}
            if r.get("resourceType") == "Patient" and r.get("id"):
                out.add(r["id"])
                break
    return out


class HttpFhirStore:
    def __init__(self, base: str = DEFAULT_BASE, cohort: set[str] | None = None,
                 timeout: int = DEFAULT_TIMEOUT):
        self.base = base.rstrip("/")
        self.cohort = cohort
        self.timeout = timeout
        self._cache: dict[tuple[str, str], list[dict]] = {}

    @classmethod
    def from_dir(cls, fhir_dir: str, base: str = DEFAULT_BASE, **kw) -> "HttpFhirStore":
        """Mirror `FhirStore(fhir_dir)`: same cohort, data served over HTTP."""
        return cls(base=base, cohort=cohort_ids(fhir_dir), **kw)

    # ---- transport ---------------------------------------------------------
    def _get(self, path: str, **params) -> dict:
        params.setdefault("_format", "json")
        url = "%s%s?%s" % (self.base, path, urllib.parse.urlencode(params))
        with urllib.request.urlopen(url, timeout=self.timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def _bundle_resources(self, resource_type: str, pid: str) -> list[dict]:
        """Every resource of a type for one patient, following pagination."""
        key = (resource_type, pid)
        if key in self._cache:
            return self._cache[key]
        out: list[dict] = []
        page = self._get("/" + resource_type, subject="Patient/" + pid, _count=str(PAGE))
        while True:
            out.extend((e.get("resource") or {}) for e in (page.get("entry") or []))
            nxt = None
            for link in (page.get("link") or []):
                if link.get("relation") == "next":
                    nxt = link.get("url")
            if not nxt:
                break
            with urllib.request.urlopen(nxt, timeout=self.timeout) as r:
                page = json.loads(r.read().decode("utf-8"))
        self._cache[key] = out
        return out

    # ---- the two methods Environment uses ---------------------------------
    def search(self, pid: str, resource_type: str,
               code_substr: str | None = None) -> list[dict]:
        """Simplified records, shaped exactly as FhirStore.search returns them."""
        if self.cohort is not None and pid not in self.cohort:
            return []                      # same as an unknown id on disk

        if resource_type == "Patient":
            try:
                p = self._get("/Patient/" + pid)
            except Exception:              # noqa: BLE001 - absent behaves as absent
                return []
            nm = (p.get("name") or [{}])[0]
            name = "%s %s" % (" ".join(nm.get("given", [])), nm.get("family", ""))
            mrn = None
            for ident in p.get("identifier", []):
                if (ident.get("type") or {}).get("text") == "Medical Record Number":
                    mrn = ident.get("value")
            return [{
                "id": p.get("id"),
                "mrn": mrn,
                "name": name.strip(),
                "gender": p.get("gender"),
                "birthDate": p.get("birthDate"),
            }]

        if resource_type == "Condition":
            out = []
            for r in self._bundle_resources("Condition", pid):
                t = (r.get("code") or {}).get("text")
                if t:                       # the disk parser's filter, kept
                    out.append({"text": t})
            return out

        if resource_type == "MedicationRequest":
            out = []
            for r in self._bundle_resources("MedicationRequest", pid):
                t = (r.get("medicationCodeableConcept") or {}).get("text")
                if t:                       # 29 on the server, 27 on disk
                    out.append({"text": t, "note": _first_note(r)})
            return out

        if resource_type == "Observation":
            obs = []
            for r in self._bundle_resources("Observation", pid):
                code = (r.get("code") or {}).get("text")
                if not code:
                    continue
                vq = r.get("valueQuantity") or {}
                has_vq = "valueQuantity" in r
                obs.append({
                    "code": code,
                    "date": r.get("effectiveDateTime"),
                    "value": ("%s %s" % (vq.get("value"), vq.get("unit", ""))).strip()
                             if has_vq else None,
                    "value_num": vq.get("value") if has_vq else None,
                })
            obs.sort(key=lambda o: o.get("date") or "", reverse=True)
            if code_substr:
                s = code_substr.lower()
                obs = [o for o in obs if s in o["code"].lower()]
            return obs

        return []

    def latest_observation(self, pid: str, code_substr: str, within_days: int,
                           as_of: str, numeric_only: bool = False) -> dict | None:
        """Same loop as FhirStore.latest_observation, over the same records."""
        from vmag.fhir_store import _days_between      # one source of truth
        for o in self.search(pid, "Observation", code_substr):
            age = _days_between(o.get("date"), as_of)
            if age is None or not (0 <= age <= within_days):
                continue
            if numeric_only and o.get("value_num") is None:
                continue
            return o
        return None
