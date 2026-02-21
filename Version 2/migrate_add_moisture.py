import csv
from datetime import datetime, timedelta

DATE_FMT = "%Y-%m-%d"

# -----------------------------
# User-adjustable settings
# -----------------------------
THRESHOLD = 10.0      # Same as settings.json
PERIOD_DAYS = 7       # Same as settings.json
DECAY = THRESHOLD / PERIOD_DAYS

INPUT_FILE = "rain_data.csv"
OUTPUT_FILE = "rain_data_migrated.csv"


def effective_mm(rec):
    """Return effective rainfall from Rain_mm or BOM_mm."""
    for key in ("Rain_mm", "BOM_mm"):
        raw = rec.get(key, "").strip()
        try:
            val = float(raw)
            if val >= 0:
                return val
        except:
            pass
    return 0.0


def load_records():
    records = []
    with open(INPUT_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)

    # Sort by date
    records.sort(key=lambda r: datetime.strptime(r["Date"], DATE_FMT).date())
    return records


def migrate(records):
    """Compute static moisture for each day and return updated records."""
    updated = []
    prev_moisture = 0.0

    for rec in records:
        d_obj = datetime.strptime(rec["Date"], DATE_FMT).date()
        eff = effective_mm(rec)

        # If watered → reset moisture to threshold
        if rec.get("Watered", "No") == "Yes":
            moisture = THRESHOLD
        else:
            # Apply decay
            moisture = max(0.0, prev_moisture - DECAY)
            # Add rainfall
            moisture += eff
            # Cap at threshold
            if moisture > THRESHOLD:
                moisture = THRESHOLD

        # Store moisture
        rec["Moisture"] = f"{moisture:.2f}"
        updated.append(rec)

        prev_moisture = moisture

    return updated


def save_records(records):
    fieldnames = ["Date", "Rain_mm", "BOM_mm", "Notes", "Watered", "Moisture"]
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for rec in records:
            writer.writerow(rec)


def main():
    print("Loading records...")
    records = load_records()

    print("Computing moisture values...")
    migrated = migrate(records)

    print(f"Saving migrated file as {OUTPUT_FILE} ...")
    save_records(migrated)

    print("\nMigration complete!")
    print("Review the new file, then replace rain_data.csv with rain_data_migrated.csv if satisfied.")


if __name__ == "__main__":
    main()