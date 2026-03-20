# Neuro Environment

This document records the baseline local environment used for ClinicalClaw's
current neuro MRI preprocessing and T1-first workflow work.

## Virtual Environment

Path:

```text
.venv-neuro
```

Create and activate:

```bash
python3 -m venv .venv-neuro
source .venv-neuro/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements-neuro.txt
```

## System Packages

Installed with Homebrew:

```bash
brew install dcm2niix nextflow
```

Verified commands:

- `dcm2niix`
- `nextflow`
- `dcm2bids` when the `.venv-neuro` environment is activated

## Python Packages

Validated imports in `.venv-neuro`:

- `torch`
- `monai`
- `nibabel`
- `pydicom`
- `SimpleITK`
- `dcm2bids`
- `bids`
- `openai`
- `fastapi`

## Current Limitations

- `highdicom` is not part of the default local install on this machine.
- The attempted install failed while building `pyjpegls`, with a missing C++
  standard library header during wheel compilation.
- FreeSurfer, FastSurfer, and DeepPrep were not auto-installed as part of this
  baseline environment.
- The current baseline supports:
- raw DICOM to NIfTI planning and execution via `dcm2niix`
- DICOM to BIDS conversion support via `dcm2bids`
- Nextflow-backed workflow planning
- MONAI / PyTorch-based Python-side processing

## Recommended Next Installs

In priority order:

1. `dcm2bids`
2. FreeSurfer or FreeSurfer Clinical
3. FastSurfer
4. ANTs
5. DeepPrep
