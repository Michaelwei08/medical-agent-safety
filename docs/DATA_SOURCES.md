# Data Sources

All data in this project is **public and synthetic**. No PHI, no controlled-access
data, no PhysioNet credentialing.

| Source | Role in VMAG | Kind | License | Access |
| --- | --- | --- | --- | --- |
| **Synthea** | Generates the synthetic FHIR R4 patient cohort the agent environment serves | Fully synthetic | Apache-2.0 | Open download / self-generate; no restrictions |
| **MedAgentBench** | Reference for the FHIR REST action space + comparison benchmark (300 physician tasks) | Realistic virtual EHR | MIT | Public GitHub clone |
| MedQA / MedMCQA | Clinical content reference for authoring vignettes | Public QA | Open | Public |
| HealthBench (OpenAI) | Evaluation-methodology reference only (rubric grading) | — | see note | Do **not** republish cases verbatim (canary string) |

## Deliberately excluded (require credentialing → not "public")

- **MIMIC-IV / MIMIC-IV-FHIR / eICU** — PhysioNet credentialing + CITI training + DUA.
- **AgentClinic-MIMIC-IV** split and **FHIR-AgentBench** — grounded in MIMIC-IV, so gated.

These are viable later (CITI training is ~1 day) but violate the current public-only constraint.

## Reproduction

From the repo root (Java 17+ and Python 3.10+):

```powershell
# 1. Synthea generator (~188 MB jar)
curl -sSL -o tools/synthea-with-dependencies.jar `
  https://github.com/synthetichealth/synthea/releases/download/master-branch-latest/synthea-with-dependencies.jar

# 2. Deterministic 12-patient FHIR cohort (seed=1)
java -jar tools/synthea-with-dependencies.jar -s 1 -p 12 `
  --exporter.baseDirectory ./data/synthea `
  --exporter.fhir.export true --exporter.hospital.fhir.export false `
  --exporter.practitioner.fhir.export false

# 3. Patient index used to author cases
python scripts/build_patient_index.py

# 4. MedAgentBench (comparison substrate)
git clone --depth 1 https://github.com/stanfordmlgroup/MedAgentBench.git third_party/MedAgentBench

# 5. Run the evaluation
python -m vmag.run_eval
```

The seed (`-s 1`) makes patient generation deterministic, so the patient UUIDs
referenced by `benchmark/cases/*.json` are reproducible.

## Sources

- Synthea: https://github.com/synthetichealth/synthea · https://synthea.mitre.org/downloads
- MedAgentBench: https://github.com/stanfordmlgroup/MedAgentBench · https://arxiv.org/abs/2501.14654
- AgentClinic: https://agentclinic.github.io/
- FHIR-AgentBench: https://arxiv.org/abs/2509.19319
- HealthBench: https://openai.com/index/healthbench/
- MIMIC-IV credentialing: https://physionet.org/content/mimiciv/3.1/
