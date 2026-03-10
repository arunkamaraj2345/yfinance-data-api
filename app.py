from flask import Flask, request, jsonify
import yfinance as yf
import pandas as pd
import re
import os
import time
from datetime import datetime, timedelta

app = Flask(__name__)

# --------------------------------------------------
# PATHS
# --------------------------------------------------

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
MERGE_DIR = os.path.join(BASE_DIR, "merge")

os.makedirs(MERGE_DIR, exist_ok=True)

# --------------------------------------------------
# MERGE FILE SCANNER
#
# Merge files are named: YYYY-MM-DD.csv
# Each file contains columns:
#   symbol, close, open, high, low, volume
#
# Scans the merge folder and returns only files
# whose date falls within [start_date, end_date].
# Returns dict: { date -> filepath }
# --------------------------------------------------

MERGE_FILENAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.csv$")

# Fields that can be sourced from the merge file.
# Key   = field name as the caller requests it (yfinance casing)
# Value = column name in the merge CSV (lowercase)
MERGE_FIELD_MAP = {
    "Close":  "close",
    "Open":   "open",
    "High":   "high",
    "Low":    "low",
    "Volume": "volume"
}


def scan_merge_files(start_date, end_date):
    """
    Scans merge/ folder for files named YYYY-MM-DD.csv
    whose date falls within [start_date, end_date] inclusive.

    Returns dict { date (date object) -> filepath (str) }
    Returns empty dict if no qualifying files are found.
    """
    result = {}

    if not os.path.isdir(MERGE_DIR):
        return result

    for fname in os.listdir(MERGE_DIR):
        m = MERGE_FILENAME_RE.match(fname)
        if not m:
            continue

        date_str = m.group(1)

        try:
            file_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue

        # Only include files within [start_date, end_date]
        if start_date <= file_date <= end_date:
            result[file_date] = os.path.join(MERGE_DIR, fname)

    return result


def normalize_symbol(symbol):
    """Normalise symbol to uppercase with .NS suffix if needed."""
    symbol = str(symbol).strip().upper()
    if symbol.endswith(".NS") or symbol.endswith(".BO"):
        return symbol
    return symbol + ".NS"


def get_merge_rows(symbol, merge_files, existing_dates, fields, fast_info):
    """
    For a given symbol, checks each qualifying merge file and builds
    additional rows for dates missing from the yfinance data.

    Parameters:
        symbol         : Normalised stock symbol (uppercase, with .NS/.BO)
        merge_files    : dict { date -> filepath } from scan_merge_files()
        existing_dates : set of date objects already in yfinance df
        fields         : list of field names the caller requested
        fast_info      : yfinance fast_info object (already fetched, reused)

    Returns:
        List of [date_str, val1, val2, ...] rows — one per missing date.
    """
    extra_rows = []

    for file_date, filepath in sorted(merge_files.items()):

        # Skip if yfinance already has this date — no duplicate insertion
        if file_date in existing_dates:
            continue

        # Read the merge file
        try:
            mdf = pd.read_csv(filepath)
        except Exception as e:
            print(f"  [MERGE WARNING] Could not read {filepath}: {e}")
            continue

        # Normalise column names to lowercase
        mdf.columns = [c.strip().lower() for c in mdf.columns]

        # Must have a symbol column to match against
        if "symbol" not in mdf.columns:
            print(f"  [MERGE WARNING] No 'symbol' column in {filepath}. Skipping.")
            continue

        # Normalise symbols in the merge file for matching
        mdf["symbol"] = mdf["symbol"].apply(normalize_symbol)

        # Find the row for this symbol
        symbol_rows = mdf[mdf["symbol"] == symbol]

        if symbol_rows.empty:
            # Symbol not in this merge file — skip silently
            continue

        # Take the first matching row
        merge_row = symbol_rows.iloc[0]

        # Build the response entry for this date
        date_str = file_date.strftime("%Y-%m-%d")
        entry    = [date_str]

        for field in fields:

            # --- Source from merge file columns ---
            if field in MERGE_FIELD_MAP:
                col = MERGE_FIELD_MAP[field]    # e.g. "Close" -> "close"
                if col in mdf.columns:
                    val = merge_row[col]
                    try:
                        entry.append(float(val))
                    except (ValueError, TypeError):
                        entry.append("NIL")
                else:
                    # Merge file doesn't have this column
                    entry.append("NIL")
                continue

            # --- Source from fast_info (same object already fetched) ---
            if field.lower() == "52weekhigh":
                try:
                    entry.append(float(fast_info.get("yearHigh", "NIL")))
                except (ValueError, TypeError):
                    entry.append("NIL")
                continue

            if field.lower() == "52weeklow":
                try:
                    entry.append(float(fast_info.get("yearLow", "NIL")))
                except (ValueError, TypeError):
                    entry.append("NIL")
                continue

            if field == "marketCap":
                try:
                    entry.append(float(fast_info.get("marketCap", "NIL")))
                except (ValueError, TypeError):
                    entry.append("NIL")
                continue

            # --- Unknown field ---
            entry.append("NIL")

        extra_rows.append(entry)

    return extra_rows


# ============================
# SERVER STATUS ENDPOINT (UNCHANGED)
# ============================

@app.route('/status', methods=['GET'])
def status():
    try:
        print("=== SERVER WARMUP START ===")

        ticker = yf.Ticker("RELIANCE.NS")

        # Warm price endpoint
        ticker.history(period="5d")

        # micro sleep (human-like)
        time.sleep(2)

        # Warm fast_info endpoint (used in your API)
        _ = ticker.fast_info

        # Stabilize connection pool
        time.sleep(2)

        print("=== SERVER WARMUP COMPLETE ===")

        return jsonify({
            "status":        "server on",
            "warmup status": "server warm",
            "time":          datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    except Exception as e:
        return jsonify({
            "status":        "server on",
            "warmup status": "warmup failed",
            "error":         str(e)
        }), 500


# ============================
# MAIN DATA ENDPOINT
# ============================

@app.route('/get_stock_data_between_dates', methods=['GET'])
def get_stock_data_between_dates():

    symbol = request.args.get('symbol')
    start  = request.args.get('start')
    end    = request.args.get('end')

    extra_fields = request.args.get('fields')
    if extra_fields:
        fields = [f.strip() for f in extra_fields.split(",")]
    else:
        fields = ["Close"]

    if not symbol or not start or not end:
        return jsonify({"error": "Missing parameters: symbol, start, end"})

    try:

        # --------------------------------------------------
        # PARSE DATES
        # Needed for merge file scanning.
        # The original code only used start/end as raw strings
        # passed to yfinance — parsing them here adds no side
        # effects to the existing fetch logic.
        # --------------------------------------------------
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d").date()
            end_date   = datetime.strptime(end,   "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."})

        # --------------------------------------------------
        # FETCH FROM YFINANCE (COMPLETELY UNCHANGED)
        # --------------------------------------------------
        ticker = yf.Ticker(symbol)
        df     = ticker.history(start=start, end=end, auto_adjust=False).reset_index()

        # fast_info fetched once — reused for both main rows
        # and merge rows that need 52weekhigh/low or marketCap.
        fast_info = ticker.fast_info

        if "Date" in df.columns:
            df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

        # --------------------------------------------------
        # SCAN MERGE FOLDER
        # Collects files whose date falls within [start, end].
        # If none found, merge_files is empty and merge is
        # skipped entirely — zero impact on normal flow.
        # --------------------------------------------------
        merge_files = scan_merge_files(start_date, end_date)

        # --------------------------------------------------
        # COLLECT EXISTING DATES FROM YFINANCE
        # Used as a duplicate guard in the merge step.
        # --------------------------------------------------
        existing_dates = set()
        if not df.empty:
            existing_dates = {
                datetime.strptime(d, "%Y-%m-%d").date()
                for d in df["Date"]
            }

        # --------------------------------------------------
        # BUILD RESULT FROM YFINANCE DATA (UNCHANGED LOGIC)
        # --------------------------------------------------
        result = [["Date"] + fields]

        if not df.empty:
            for _, row in df.iterrows():
                entry = [row["Date"]]

                for field in fields:

                    if field in df.columns:
                        entry.append(float(row[field]))
                        continue

                    if field.lower() == "52weekhigh":
                        entry.append(float(fast_info.get("yearHigh", "NIL")))
                        continue

                    if field.lower() == "52weeklow":
                        entry.append(float(fast_info.get("yearLow", "NIL")))
                        continue

                    if field == "marketCap":
                        entry.append(float(fast_info.get("marketCap", "NIL")))
                        continue

                    entry.append("NIL")

                result.append(entry)

        # --------------------------------------------------
        # MERGE STEP
        # Only runs if qualifying merge files were found.
        # For each merge file date not already in yfinance:
        #   - Looks up this symbol in the merge CSV.
        #   - Builds a response row using merge file values
        #     for Close/Open/High/Low/Volume fields, and
        #     fast_info for 52weekhigh/52weeklow/marketCap.
        #   - Appends the row to the result.
        # After all merge rows are added, re-sorts by date.
        # --------------------------------------------------
        if merge_files:
            norm_symbol = normalize_symbol(symbol)
            merged_rows = get_merge_rows(
                norm_symbol,
                merge_files,
                existing_dates,
                fields,
                fast_info
            )

            if merged_rows:
                # Detach header, combine data rows, re-sort by date, reattach header
                all_data_rows = result[1:] + merged_rows
                all_data_rows.sort(key=lambda r: r[0])  # date strings sort correctly as YYYY-MM-DD
                result = [result[0]] + all_data_rows

        # --------------------------------------------------
        # GUARD: no data from either yfinance or merge
        # --------------------------------------------------
        if len(result) <= 1:
            return jsonify({
                "error": f"No data found for {symbol} between {start} and {end}."
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)})


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
