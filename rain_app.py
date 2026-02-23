import csv
import os

from datetime import date, datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox
import json

from tkcalendar import DateEntry

SETTINGS_FILE = "settings.json"

def load_settings():
    # Default settings
    defaults = {
        "data_file": "rain_data.csv",
        "threshold_mm": 10.0, # Steve's rule of thumb for lawn watering = 10 mm
        "period_days": 7 # Steve's rule of thumb for lawn watering = 7 days
}

    if not os.path.exists(SETTINGS_FILE):
        return defaults

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
    except:
        return defaults

    # Merge defaults with loaded settings
    for key, value in defaults.items():
        if key not in loaded:
            loaded[key] = value

    return loaded

def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4)
        
DATE_FMT = "%Y-%m-%d"  # storage format

class RainApp(tk.Tk):
    def __init__(self):
        super().__init__()

        # Load settings FIRST
        self.settings = load_settings()
        # Now you can safely use settings
        self.data_file = self.settings["data_file"]
        
        self.title("Rainfall Logger")
        self.geometry("900x600")
        try:
            self.iconbitmap("rain.ico")
        except Exception:
            # Ignore missing or invalid icon on systems without the file
            pass

        self.records = []  # list of dicts

        self._build_ui()
        self._load_data()
        self._refresh_table()
        self._update_dashboard()
        
    # ---------- Data layer ----------
    def _load_data(self):
        self.records.clear()
        if not os.path.exists(self.data_file):
            return
        with open(self.data_file, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rec = {
                    "Date": row.get("Date", ""),
                    "Rain_mm": row.get("Rain_mm", ""),
                    "BOM_mm": row.get("BOM_mm", ""),
                    "Notes": row.get("Notes", ""),
                    "Watered": row.get("Watered", "No"),
                    "Moisture": row.get("Moisture", ""),   # NEW
                }
                self.records.append(rec)
        self._sort_records()

    def _save_data(self):
        fieldnames = ["Date", "Rain_mm", "BOM_mm", "Notes", "Watered", "Moisture"]
        with open(self.data_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for rec in self.records:
                writer.writerow(rec)

    def _sort_records(self):
        def parse_date(d):
            try:
                return datetime.strptime(d, DATE_FMT).date()
            except Exception:
                return date.min

        self.records.sort(key=lambda r: parse_date(r["Date"]))

    def _effective_mm(self, rec):
        """Return effective rainfall:
           1. Use Rain_mm if it's a number >= 0
           2. Else use BOM_mm if it's a number >= 0
           3. Else return None (invalid)
        """
        rain_raw = rec.get("Rain_mm", "").strip()
        bom_raw = rec.get("BOM_mm", "").strip()

        # Try Rain_mm first
        try:
            rain_val = float(rain_raw)
            if rain_val >= 0:
                return rain_val
        except ValueError:
            pass

        # Try BOM_mm next
        try:
            bom_val = float(bom_raw)
            if bom_val >= 0:
                return bom_val
        except ValueError:
            pass

        # Neither valid
        return None

    def _compute_daily_moisture(self, prev_moisture, eff_rain):
        """
        Compute today's moisture based on:
        - previous day's stored moisture
        - today's effective rainfall
        - decay = threshold / period_days
        """
        try:
            threshold = float(self.settings.get("threshold_mm", 20.0))
        except ValueError:
            threshold = 20.0

        try:
            period_days = int(self.settings.get("period_days", 5))
            if period_days <= 0:
                period_days = 5
        except ValueError:
            period_days = 5

        decay = threshold / period_days

        # Apply decay
        moisture = max(0, prev_moisture - decay)

        # Add rainfall
        if eff_rain is not None:
            moisture += eff_rain

        # Cap at threshold
        if moisture > threshold:
            moisture = threshold

        return moisture

    def _recompute_from(self, start_date):
        """
        Recompute moisture from start_date forward, using stored settings.
        Used when a historical row is edited or settings are changed.
        """
        # Sort to ensure correct order
        self._sort_records()

        # Find index of start_date
        start_idx = None
        for i, rec in enumerate(self.records):
            if rec["Date"] == start_date.strftime(DATE_FMT):
                start_idx = i
                break

        if start_idx is None:
            return  # nothing to do

        # Determine previous day's moisture
        if start_idx == 0:
            prev_moisture = 0.0
        else:
            try:
                prev_moisture = float(self.records[start_idx - 1].get("Moisture", 0.0))
            except ValueError:
                prev_moisture = 0.0

        # Recompute forward
        for i in range(start_idx, len(self.records)):
            rec = self.records[i]
            eff = self._effective_mm(rec)

            if rec.get("Watered", "No") == "Yes":
                moisture = float(self.settings.get("threshold_mm", 20.0))
            else:
                moisture = self._compute_daily_moisture(prev_moisture, eff)

            rec["Moisture"] = f"{moisture:.2f}"
            prev_moisture = moisture

        """
        Computes soil moisture balance using decay derived from Steve's rule:
        decay_per_day = threshold_mm / period_days.
        """
        try:
            threshold = float(self.settings.get("threshold_mm", 20.0))  # T
        except ValueError:
            threshold = 20.0

        try:
            period_days = int(self.settings.get("period_days", 5))      # N
            if period_days <= 0:
                period_days = 5
        except ValueError:
            period_days = 5

        decay = threshold / period_days                                 # T/N

        # Find last watering date
        last_watered = None
        for rec in reversed(self.records):
            if rec.get("Watered", "No") == "Yes":
                try:
                    last_watered = datetime.strptime(rec["Date"], DATE_FMT).date()
                except ValueError:
                    continue
                break

        if last_watered is None:
            return None  # No watering history

        # Start at full moisture
        balance = threshold

        # Build a lookup for rainfall by date
        rain_lookup = {}
        for r in self.records:
            try:
                d_obj = datetime.strptime(r["Date"], DATE_FMT).date()
            except ValueError:
                continue
            eff = self._effective_mm(r)
            if eff is None:
                eff = 0
            rain_lookup[d_obj] = rain_lookup.get(d_obj, 0) + eff

        today = date.today()
        day = last_watered

        while day < today:
            day += timedelta(days=1)

            # Apply decay
            balance -= decay
            if balance < 0:
                balance = 0

            # Add rainfall if present
            if day in rain_lookup:
                balance += rain_lookup[day]
                if balance > threshold:
                    balance = threshold

        return balance

        balance = self._compute_moisture_balance()
        if balance is None:
            return "Unknown"
        return "YES – Water Lawn" if balance <= 0 else "No watering needed"
    
        rain_raw = rec.get("Rain_mm", "").strip()
        bom_raw = rec.get("BOM_mm", "").strip()

        # Try Rain_mm first
        try:
            rain_val = float(rain_raw)
            if rain_val >= 0:
                return rain_val
        except ValueError:
            pass

        # Try BOM_mm next
        try:
            bom_val = float(bom_raw)
            if bom_val >= 0:
                return bom_val
        except ValueError:
            pass

        # Neither valid
        return None

    # ---------- UI construction ----------
    def _build_ui(self):
        # Top frame: input form
        form_frame = tk.Frame(self)
        form_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

        tk.Label(form_frame, text="Date:").grid(row=0, column=0, sticky="e")

        self.entry_date = DateEntry(
            form_frame,
            width=12,
            date_pattern="yyyy-mm-dd",   # matches your storage format
            maxdate=date.today(),        # prevents future dates in the picker
        )
        self.entry_date.grid(row=0, column=1, padx=5)

        tk.Label(form_frame, text="Rain_mm (user):").grid(row=0, column=2, sticky="e")
        self.entry_rain = tk.Entry(form_frame, width=8)
        self.entry_rain.grid(row=0, column=3, padx=5)

        tk.Label(form_frame, text="BOM_mm:").grid(row=0, column=4, sticky="e")
        self.entry_bom = tk.Entry(form_frame, width=8)
        self.entry_bom.grid(row=0, column=5, padx=5)

        tk.Label(form_frame, text="Notes:").grid(row=1, column=0, sticky="e")
        self.entry_notes = tk.Entry(form_frame, width=50)
        self.entry_notes.grid(row=1, column=1, columnspan=5, sticky="w", padx=5, pady=3)

        self.var_watered = tk.BooleanVar()
        tk.Checkbutton(form_frame, text="Watered today", variable=self.var_watered)\
            .grid(row=2, column=0, columnspan=2, sticky="w", pady=3)

        btn_add = tk.Button(form_frame, text="Add / Update", command=self._on_add_update)
        btn_add.grid(row=0, column=6, padx=10)

        btn_delete = tk.Button(form_frame, text="Delete Selected", command=self._on_delete)
        btn_delete.grid(row=1, column=6, padx=10)

        # Middle frame: table
        table_frame = tk.Frame(self)
        table_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ("Date", "Rain_mm", "BOM_mm", "Effective_mm", "Moisture", "Notes", "Watered")
        
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100 if col != "Notes" else 250, anchor="center")
            self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<<TreeviewSelect>>", self._on_select_row)

        self.tree.tag_configure("watered", background="#90EE90")       # PaleGreen2
        self.tree.tag_configure("rain", background="#87CEFA")          # LightSkyBlue
        self.tree.tag_configure("dry", background="#FFDEAD")           # NavajoWhite
        
        # Bottom frame: dashboard
        dash_frame = tk.LabelFrame(self, text="Dashboard")
        dash_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)

        # Row 0
        tk.Label(dash_frame, text="Period (days):").grid(row=0, column=0, sticky="e")
        self.entry_period = tk.Entry(dash_frame, width=6)
        self.entry_period.grid(row=0, column=1, padx=5)
        self.entry_period.insert(0, str(self.settings.get("period_days", 5)))

        tk.Label(dash_frame, text="Threshold (mm):").grid(row=0, column=2, sticky="e")
        self.entry_threshold = tk.Entry(dash_frame, width=6)
        self.entry_threshold.grid(row=0, column=3, padx=5)
        self.entry_threshold.insert(0, str(self.settings["threshold_mm"]))

        # Row 1
        tk.Label(dash_frame, text="Moisture balance:").grid(row=1, column=0, sticky="e")
        self.lbl_moisture_balance = tk.Label(dash_frame, text="0.0")
        self.lbl_moisture_balance.grid(row=1, column=1, sticky="w")

        tk.Label(dash_frame, text="Watering Needed?:").grid(row=1, column=2, sticky="e")
        self.lbl_watering = tk.Label(dash_frame, text="Unknown", width=18)
        self.lbl_watering.grid(row=1, column=3, sticky="w")

        # Row 2 — Last watering date
        tk.Label(dash_frame, text="Last watering date:").grid(row=2, column=0, sticky="e")
        self.lbl_last_watering = tk.Label(dash_frame, text="-")
        self.lbl_last_watering.grid(row=2, column=1, sticky="w")
        tk.Label(dash_frame, text="Days since last watering:").grid(row=2, column=2, sticky="e")
        self.lbl_days_since_watering = tk.Label(dash_frame, text="-")
        self.lbl_days_since_watering.grid(row=2, column=3, sticky="w")

        # Row 3 — Last rainfall date + days since
        tk.Label(dash_frame, text="Last rainfall date:").grid(row=3, column=0, sticky="e")
        self.lbl_last_rain_date = tk.Label(dash_frame, text="-")
        self.lbl_last_rain_date.grid(row=3, column=1, sticky="w")

        tk.Label(dash_frame, text="Days since last rain:").grid(row=3, column=2, sticky="e")
        self.lbl_days_since = tk.Label(dash_frame, text="-")
        self.lbl_days_since.grid(row=3, column=3, sticky="w")

        # Row 4 — Missing days
        tk.Label(dash_frame, text="Missing days:").grid(row=4, column=0, sticky="e")
        self.lbl_missing = tk.Label(dash_frame, text="-")
        self.lbl_missing.grid(row=4, column=1, sticky="w")

        self.btn_show_missing = tk.Button(dash_frame, text="Show Missing Dates", command=self._show_missing_dates)
        self.btn_show_missing.grid(row=4, column=2, columnspan=2, pady=3)

        # --- Legend ---
        legend = tk.Frame(dash_frame)
        legend.grid(row=5, column=0, columnspan=4, pady=(10, 5), sticky="w")

        # Watered (overrides everything)
        tk.Label(legend, text="  ", bg="#90EE90", width=2).grid(row=0, column=0, padx=2)
        tk.Label(legend, text="Watered").grid(row=0, column=1, sticky="w", padx=(0, 10))

        # Rain > 0
        tk.Label(legend, text="  ", bg="#87CEFA", width=2).grid(row=0, column=2, padx=2)
        tk.Label(legend, text="Rain > 0 mm").grid(row=0, column=3, sticky="w", padx=(0, 10))

        # Rain = 0
        tk.Label(legend, text="  ", bg="#FFDEAD", width=2).grid(row=0, column=4, padx=2)
        tk.Label(legend, text="Rain = 0 mm").grid(row=0, column=5, sticky="w")

        # Recalculate dashboard when period or threshold changes
        self.entry_threshold.bind("<FocusOut>", lambda e: self._update_dashboard())
        self.entry_period.bind("<FocusOut>", lambda e: self._update_dashboard())

    # ---------- UI actions ----------
    def _on_add_update(self):
        d_str = self.entry_date.get().strip()
        rain_str = self.entry_rain.get().strip()
        bom_str = self.entry_bom.get().strip()
        notes_str = self.entry_notes.get().strip()
        watered_flag = "Yes" if self.var_watered.get() else "No"
        
        # Validate date
        try:
            d_obj = datetime.strptime(d_str, DATE_FMT).date()
        except ValueError:
            messagebox.showerror("Invalid Date", "Please enter date as YYYY-MM-DD.")
            return
        
        # Prevent future dates
        if d_obj > date.today():
            messagebox.showerror("Invalid Date", "Future dates are not allowed.")
            return

        # Validate numeric fields if not blank
        for label, val in [("Rain_mm", rain_str), ("BOM_mm", bom_str)]:
            if val != "":
                try:
                    float(val)
                except ValueError:
                    messagebox.showerror("Invalid Value", f"{label} must be a number or blank.")
                    return
                
        # Validate that at least one of Rain_mm or BOM_mm is a number >= 0
        valid_rain = False
        valid_bom = False

        try:
            if rain_str != "":
                if float(rain_str) >= 0:
                    valid_rain = True
        except ValueError:
            pass

        try:
            if bom_str != "":
                if float(bom_str) >= 0:
                    valid_bom = True
        except ValueError:
            pass

        if not valid_rain and not valid_bom:
            messagebox.showerror(
                "Invalid Data",
                "You must enter at least one valid rainfall value (Rain_mm or BOM_mm ≥ 0)."
            )
            return

        # --- Compute moisture for this date ---

        # 1. Determine previous day's moisture
        prev_moisture = 0.0
        yesterday = d_obj - timedelta(days=1)

        for r in self.records:
            if r["Date"] == yesterday.strftime(DATE_FMT):
                try:
                    prev_moisture = float(r.get("Moisture", 0.0))
                except ValueError:
                    prev_moisture = 0.0
                break

        # 2. Effective rainfall for today
        eff_today = None
        try:
            if rain_str != "":
                eff_today = float(rain_str)
            elif bom_str != "":
                eff_today = float(bom_str)
        except:
            eff_today = None

        # 3. If watered today → reset moisture to threshold
        if watered_flag == "Yes":
            moisture_today = float(self.settings.get("threshold_mm", 20.0))
        else:
            moisture_today = self._compute_daily_moisture(prev_moisture, eff_today)

        # --- Upsert record ---
        found = False
        for rec in self.records:
            if rec["Date"] == d_obj.strftime(DATE_FMT):
                rec["Rain_mm"] = rain_str
                rec["BOM_mm"] = bom_str
                rec["Notes"] = notes_str
                rec["Watered"] = watered_flag
                rec["Moisture"] = f"{moisture_today:.2f}"
                found = True
                break
        
        if not found:
            self.records.append({
                "Date": d_obj.strftime(DATE_FMT),
                "Rain_mm": rain_str,
                "BOM_mm": bom_str,
                "Notes": notes_str,
                "Watered": watered_flag,
                "Moisture": f"{moisture_today:.2f}",
            })

        # Recompute moisture forward from this date
        self._recompute_from(d_obj)
        
        self._sort_records()
        self._save_data()
        self._refresh_table()
        self._update_dashboard()

    def _on_delete(self):
        sel = self.tree.selection()
        if not sel:
            return
        item_id = sel[0]
        values = self.tree.item(item_id, "values")
        d_str = values[0]
        self.records = [r for r in self.records if r["Date"] != d_str]
        self._save_data()
        self._refresh_table()
        self._update_dashboard()

    def _on_select_row(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        item_id = sel[0]
        values = self.tree.item(item_id, "values")
        try:
            # DateEntry supports set_date; prefer that over manipulating contents
            self.entry_date.set_date(values[0])
        except Exception:
            self.entry_date.delete(0, tk.END)
            self.entry_date.insert(0, values[0])
        self.entry_rain.delete(0, tk.END)
        self.entry_rain.insert(0, values[1])
        self.entry_bom.delete(0, tk.END)
        self.entry_bom.insert(0, values[2])
        self.entry_notes.delete(0, tk.END)
        self.entry_notes.insert(0, values[5])
        # Restore the watered checkbox from the selected row (values[6])
        try:
            watered_val = values[6]
        except Exception:
            watered_val = "No"
        self.var_watered.set(True if str(watered_val).strip().lower() == "yes" else False)
    

    # ---------- Table & dashboard refresh ----------

    def _refresh_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        for rec in self.records:
            eff = self._effective_mm(rec)
            eff_str = "" if eff is None else f"{eff:.1f}"

            # Determine tag priority
            if rec.get("Watered", "No") == "Yes":
                tags = ("watered",)
            else:
                if eff is None:
                    tags = ()  # invalid data, no colour
                elif eff > 0:
                    tags = ("rain",)
                else:
                    tags = ("dry",)

            self.tree.insert(
                "",
                tk.END,
                values=(
                    rec["Date"],
                    rec["Rain_mm"],
                    rec["BOM_mm"],
                    eff_str,
                    rec.get("Moisture", ""),
                    rec["Notes"],
                    rec["Watered"],
                ),
                tags=tags
            )
            
        # ✅ Scroll to the bottom so latest entries are visible
        self.tree.yview_moveto(1.0)

    def _update_dashboard(self):

        # --- Threshold (mm) ---
        try:
            threshold = float(self.entry_threshold.get())
        except ValueError:
            threshold = 20.0
            self.entry_threshold.delete(0, tk.END)
            self.entry_threshold.insert(0, str(threshold))

        # --- Period (days) ---
        try:
            period_days = int(self.entry_period.get())
            if period_days <= 0:
                period_days = 5
        except ValueError:
            period_days = 5
            self.entry_period.delete(0, tk.END)
            self.entry_period.insert(0, str(period_days))

        # Save updated settings
        self.settings["threshold_mm"] = threshold
        self.settings["period_days"] = period_days
        save_settings(self.settings)

        today = date.today()
        last_watering_date = None
        last_rain_date = None

        # --- Last watering & last rainfall dates (independent of moisture model) ---
        for rec in self.records:
            try:
                d_obj = datetime.strptime(rec["Date"], DATE_FMT).date()
            except ValueError:
                continue

            eff = self._effective_mm(rec)
            if eff is not None and eff > 0:
                if last_rain_date is None or d_obj > last_rain_date:
                    last_rain_date = d_obj

            if rec.get("Watered", "No") == "Yes":
                if last_watering_date is None or d_obj > last_watering_date:
                    last_watering_date = d_obj

        # --- Moisture Mode (Stored Moisture) ---
        if self.records:
            last_rec = self.records[-1]
            try:
                balance = float(last_rec.get("Moisture", 0.0))
            except ValueError:
                balance = 0.0
        else:
            balance = 0.0

        self.lbl_moisture_balance.config(text=f"{balance:.1f} mm")

        if balance <= 0:
            self.lbl_watering.config(text="YES – Water Lawn", bg="red", fg="white")
        else:
            self.lbl_watering.config(text="No watering needed", bg="green", fg="white")

        # Last watering date + days since
        if last_watering_date is None:
            self.lbl_last_watering.config(text="-")
            self.lbl_days_since_watering.config(text="-")
        else:
            self.lbl_last_watering.config(text=last_watering_date.strftime(DATE_FMT))
            self.lbl_days_since_watering.config(text=str((today - last_watering_date).days))

        # Last rainfall date + days since
        if last_rain_date is None:
            self.lbl_last_rain_date.config(text="-")
            self.lbl_days_since.config(text="-")
        else:
            self.lbl_last_rain_date.config(text=last_rain_date.strftime(DATE_FMT))
            self.lbl_days_since.config(text=str((today - last_rain_date).days))

        # Missing days detector
        missing = self._compute_missing_dates()

        if missing:
            self.lbl_missing.config(text="Missing days detected")
            self.btn_show_missing.grid()   # show button
        else:
            self.lbl_missing.config(text="No missing days")
            self.btn_show_missing.grid_remove()   # hide button

    def _compute_missing_dates(self):
        """Return list of missing dates (as date objects) between min and max Date."""
        if not self.records:
            return []

        dates = []
        for rec in self.records:
            try:
                d_obj = datetime.strptime(rec["Date"], DATE_FMT).date()
                dates.append(d_obj)
            except ValueError:
                continue
        if not dates:
            return []

        dates = sorted(set(dates))
        all_dates = []
        d = dates[0]
        while d <= dates[-1]:
            all_dates.append(d)
            d += timedelta(days=1)

        existing = set(dates)
        missing = [d for d in all_dates if d not in existing]
        return missing

    def _show_missing_dates(self):
        missing = self._compute_missing_dates()
        if not missing:
            messagebox.showinfo("Missing Dates", "No missing days.")
            return

        win = tk.Toplevel(self)
        win.title("Missing Dates")
        txt = tk.Text(win, width=20, height=15)
        txt.pack(fill=tk.BOTH, expand=True)
        for d in missing:
            txt.insert(tk.END, d.strftime(DATE_FMT) + "\n")
        txt.config(state="disabled")


if __name__ == "__main__":
    app = RainApp()
    app.mainloop()
