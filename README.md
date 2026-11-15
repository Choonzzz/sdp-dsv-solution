# sdp-dsv-solution

Streamlit mockup of the M4 dashboard (call-out queue, lanes and staging zones). It replays one real day with synthetic forwarders, zones, pallets and arrival times. See [mockup/PRD.md](mockup/PRD.md) for the spec.

## Setup

Run from the repository root (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

The mockup data file `data/Mockup_Data.xlsx` is in the repo. To regenerate it, run all cells of `mockup/Data _Prep.ipynb`.

## Run the app

```powershell
streamlit run mockup/app.py
```

It opens at http://localhost:8501. Press `Ctrl+C` in the terminal to stop it.

If `streamlit` is not found, use the venv directly:

```powershell
.venv\Scripts\python.exe -m streamlit run mockup/app.py
```

## Run the tests

```powershell
pytest mockup -q
```
