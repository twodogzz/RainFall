# 🌧️ RainApp  
*A simple, stateful rainfall and lawn‑watering tracker for Windows*

RainApp is a lightweight desktop application for Windows 10–11 that helps homeowners track rainfall, watering events, and soil moisture conditions. It provides a clean UI for daily data entry, a colour‑coded history table, and a dashboard that estimates soil moisture using a **stateful, decay‑based model** derived from practical lawn‑care advice.

The app is designed to be transparent, auditable, and easy to maintain — no cloud services, no databases, just CSV and JSON files stored locally.

---

# 🐍 Python Version & Environment

RainApp is written in **Python 3.14** and uses:

- **tkinter** — GUI framework (standard library)  
- **tkcalendar** — date picker widget  
- **csv**, **json**, **datetime**, **os** — standard library modules  

The Windows executable is built using **PyInstaller** under Python 3.14.

To run from source:

```
Python 3.14.x
pip install tkcalendar
pip install pyinstaller   # only needed for building the EXE
```

---

# 🌱 Features

## ✔ Daily rainfall logging  
Record rainfall from two sources:

- **Rain_mm** (user‑entered)  
- **BOM_mm** (Bureau of Meteorology data)

The app automatically chooses the first valid value.

---

## ✔ Watering event tracking  
Mark any day as “Watered”.  
This resets the moisture model and is visually highlighted in the table.

---

## ✔ Colour‑coded rainfall history  
The table uses intuitive colours:

- **Green** — Watered  
- **Blue** — Rain > 0 mm  
- **Tan** — Rain = 0 mm  

---

## ✔ Moisture column (read‑only, auditable)  
The table includes a **Moisture** column showing the stored moisture value for each day.

This allows:

- Verification of calculations  
- Debugging  
- Confidence in the model’s behaviour  

---

## ✔ Stateful moisture model (static per day)  
RainApp stores a **Moisture** value for every day in the CSV.

This ensures:

- No historical rewriting  
- Settings changes affect only future days  
- Editing a past day recalculates moisture forward only  
- Moisture values remain consistent and auditable  

---

## ✔ Retrospective settings correction  
Changing **Threshold (mm)** or **Period (days)** does **not** recalculate the entire dataset.

Instead:

- The new settings apply **only to the selected row**  
- When you click **Add/Update**, moisture is recalculated **from that date forward**  
- Earlier days remain unchanged  

This allows you to fix incorrect settings used in the past.

---

## ✔ Forward‑only recalculation  
When you edit a past record:

1. That day’s moisture is recalculated  
2. All future days are recalculated  
3. Past days remain untouched  

This preserves the integrity of the moisture timeline.

---

## ✔ Dashboard summary  
The dashboard displays:

- Moisture balance (from the last record)  
- Watering needed?  
- Last watering date  
- Last rainfall date  
- Days since last rain  
- Missing days  
- A legend explaining the colour coding  

---

## ✔ Missing‑day detection  
Automatically identifies gaps in the date sequence and allows you to view missing dates.

---

# 🌦 Moisture Model (Decay‑Based, Stateful)

RainApp implements a generalised moisture‑decay model based on the rule:

> “If, over **N days** after watering, rainfall is less than **T mm**, water again.”

This is converted into a simple, explainable soil‑moisture model:

### Daily moisture calculation:
```
decay = Threshold_mm / Period_days
moisture_today = max(0, moisture_yesterday - decay)
moisture_today += effective_rainfall
moisture_today = min(moisture_today, Threshold_mm)
if watered_today: moisture_today = Threshold_mm
```

### Key properties:
- Moisture is **stored per day**  
- Settings changes do **not** rewrite history  
- Editing a past day recalculates forward only  
- Moisture values are visible and auditable  

---

# 🧩 Data Storage

RainApp uses two local files:

| File | Purpose |
|------|---------|
| `rain_data.csv` | Daily rainfall, watering, notes, and stored moisture |
| `settings.json` | Threshold, period, and data file settings |

The CSV schema:

```
Date, Rain_mm, BOM_mm, Notes, Watered, Moisture
```

---

# 🖥️ Windows 10–11 Executable Deployment

RainApp is packaged as a **stand‑alone Windows executable** using PyInstaller.

## Required Runtime Files  
Keep these files together in the same folder:

```
rain_app.exe
rain.ico
rain_data.csv
settings.json
```

## Building the Executable

From the project directory:

```
E:\SoftwareProjects\GithubRepos\RainFall
```

Run:

```
PyInstaller_cmd.bat
```

Contents of `PyInstaller_cmd.bat`:

```
py -3.14 -m PyInstaller --noconsole --onefile --icon=rain.ico rain_app.py
```

This produces:

```
dist\rain_app.exe
```

Copy the EXE and required runtime files into a deployment folder.

---

# 🔄 Migration Script (Required for older CSV files)

Older versions of RainApp did not store moisture.

Run the included migration script:

```
migrate_add_moisture.py
```

This:

- Adds the Moisture column  
- Computes moisture for all historical days  
- Produces a new CSV  
- Requires no manual editing  

After migration, rename:

```
rain_data_migrated.csv → rain_data.csv
```

---

# 📂 Project Structure

```
RainFall/
│
├── rain_app.py
├── rain_data.csv
├── settings.json
├── rain.ico
├── migrate_add_moisture.py
├── PyInstaller_cmd.bat
└── README.md
```

---

# 🚀 Getting Started

1. Clone the repository  
2. Run the migration script (only once, if upgrading)  
3. Launch `rain_app.py` with Python 3.14 **or** run `rain_app.exe`  
4. Enter rainfall and watering data daily  
5. Review the dashboard to determine watering needs  

---

# 📝 License

This project is for personal use.  
You may modify or extend it for your own lawn‑care needs.

---

