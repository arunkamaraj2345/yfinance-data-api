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

MERGE_FILENAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:\([^)]*\))?\.csv$")

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


def get_merge_rows(symbol, merge_files, df, fields, fast_info):
    """
    For a given symbol, checks each qualifying merge file and builds/replaces
    OHLCV rows.

    Rules:
      1. If Yahoo has no row for the merge-file date, add the merge row.
      2. If Yahoo has the date but ANY of Open/Close/High/Low/Volume is
         NaN or NIL, replace ALL five OHLCV values with the merge values.
      3. If Yahoo has the date and all five OHLCV values are valid, leave
         Yahoo's OHLCV values unchanged.
      4. 52weekhigh/52weeklow/marketCap continue to come from fast_info.

    Returns:
        List of [date_str, val1, val2, ...] rows for dates that need to be
        added or whose OHLCV values need to be replaced.
    """
    replacement_rows = []

    # Build a quick lookup of Yahoo rows by date.
    yahoo_rows = {}
    if not df.empty and "Date" in df.columns:
        for _, row in df.iterrows():
            yahoo_rows[row["Date"]] = row

    ohlcv_fields = ["Open", "High", "Low", "Close", "Volume"]

    def is_invalid(value):
        if value is None:
            return True

        if isinstance(value, str):
            stripped = value.strip().upper()
            if stripped in ("NIL", "NAN", ""):
                return True

        try:
            return pd.isna(value)
        except (TypeError, ValueError):
            return False

    for file_date, filepath in sorted(merge_files.items()):
        date_str = file_date.strftime("%Y-%m-%d")
        yahoo_row = yahoo_rows.get(date_str)

        # If Yahoo already has the date, only use the merge file when
        # at least one OHLCV field is NaN/NIL.
        if yahoo_row is not None:
            yahoo_ohlcv_invalid = any(
                field in df.columns and is_invalid(yahoo_row[field])
                for field in ohlcv_fields
            )

            if not yahoo_ohlcv_invalid:
                continue

        # Read the merge file.
        try:
            mdf = pd.read_csv(filepath)
        except Exception as e:
            print(f"  [MERGE WARNING] Could not read {filepath}: {e}")
            continue

        # Normalise column names to lowercase.
        mdf.columns = [c.strip().lower() for c in mdf.columns]

        # Must have a symbol column to match against.
        if "symbol" not in mdf.columns:
            print(f"  [MERGE WARNING] No 'symbol' column in {filepath}. Skipping.")
            continue

        # Normalise symbols in the merge file for matching.
        mdf["symbol"] = mdf["symbol"].apply(normalize_symbol)

        # Find the row for this symbol.
        symbol_rows = mdf[mdf["symbol"] == symbol]

        if symbol_rows.empty:
            continue

        # Take the first matching row.
        merge_row = symbol_rows.iloc[0]

        # Build the response entry for this date.
        entry = [date_str]

        for field in fields:

            # OHLCV fields come from the merge file.
            if field in MERGE_FIELD_MAP:
                col = MERGE_FIELD_MAP[field]

                if col in mdf.columns:
                    val = merge_row[col]
                    try:
                        if is_invalid(val):
                            entry.append("NIL")
                        else:
                            entry.append(float(val))
                    except (ValueError, TypeError):
                        entry.append("NIL")
                else:
                    entry.append("NIL")
                continue

            # 52-week high comes from fast_info.
            if field.lower() == "52weekhigh":
                try:
                    entry.append(float(fast_info.get("yearHigh", "NIL")))
                except (ValueError, TypeError):
                    entry.append("NIL")
                continue

            # 52-week low comes from fast_info.
            if field.lower() == "52weeklow":
                try:
                    entry.append(float(fast_info.get("yearLow", "NIL")))
                except (ValueError, TypeError):
                    entry.append("NIL")
                continue

            # Market cap comes from fast_info.
            if field == "marketCap":
                try:
                    entry.append(float(fast_info.get("marketCap", "NIL")))
                except (ValueError, TypeError):
                    entry.append("NIL")
                continue

            # Unknown field.
            entry.append("NIL")

        replacement_rows.append(entry)

    return replacement_rows


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
                df,
                fields,
                fast_info
            )

            if merged_rows:
                # Build a lookup of merge rows by date.
                merge_row_map = {row[0]: row for row in merged_rows}

                # Replace Yahoo rows for dates whose OHLCV data was invalid,
                # and append rows for dates Yahoo did not have.
                all_data_rows = []

                for row in result[1:]:
                    if row[0] in merge_row_map:
                        all_data_rows.append(merge_row_map[row[0]])
                    else:
                        all_data_rows.append(row)

                yahoo_dates = {row[0] for row in result[1:]}

                for row in merged_rows:
                    if row[0] not in yahoo_dates:
                        all_data_rows.append(row)

                all_data_rows.sort(
                    key=lambda r: r[0]
                )  # YYYY-MM-DD strings sort chronologically
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

@app.route("/versions")
def versions():
    import sys
    import flask
    import pandas
    import yfinance

    return {
        "python": sys.version,
        "flask": flask.__version__,
        "pandas": pandas.__version__,
        "yfinance": yfinance.__version__
    }


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
