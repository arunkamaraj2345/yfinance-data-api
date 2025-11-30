from flask import Flask, request, jsonify
import yfinance as yf
import pandas as pd

app = Flask(__name__)


# -------------------------------------------------------------------
# Utility functions
# -------------------------------------------------------------------
def safe_float(val):
    try:
        return float(val)
    except:
        return "NIL"


def get_yoy_quarterly_growth(df, field):
    """
    df = ticker.quarterly_financials
    field = "Total Revenue" or "Net Income"
    """
    if df is None or field not in df.index:
        return "NIL"

    series = df.loc[field].dropna().values

    # Need at least 5 quarters to compare Q0 vs Q4 (YoY same quarter comparison)
    if len(series) < 5:
        return "NIL"

    current = safe_float(series[0])
    prev_yoy = safe_float(series[4])

    if current == "NIL" or prev_yoy in ("NIL", 0):
        return "NIL"

    try:
        return round(((current - prev_yoy) / prev_yoy) * 100, 2)
    except:
        return "NIL"


# -------------------------------------------------------------------
# MAIN API
# -------------------------------------------------------------------
@app.route("/get_stock_data_between_dates", methods=["GET"])
def get_stock_data_between_dates():
    symbol = request.args.get("symbol")
    start = request.args.get("start")
    end = request.args.get("end")

    fields_param = request.args.get("fields")
    fields = [f.strip() for f in fields_param.split(",")] if fields_param else ["Close"]

    if not symbol or not start or not end:
        return jsonify({"error": "Missing parameters: symbol, start, end"})

    try:
        ticker = yf.Ticker(symbol)

        # ---------------------------------------------------------------
        # 1️⃣ PRICE DATA (Always from history → auto_adjust = FALSE)
        # ---------------------------------------------------------------
        df = ticker.history(start=start, end=end, auto_adjust=False).reset_index()

        if df.empty:
            return jsonify({"error": f"No data found for {symbol}."})

        # ---------------------------------------------------------------
        # 2️⃣ METADATA (fast_info, info, fundamentals)
        # ---------------------------------------------------------------
        fast_info = ticker.fast_info or {}
        info = ticker.info or {}

        # Quarterly fundamentals
        try:
            qf = ticker.quarterly_financials
        except:
            qf = None

        # YoY quarterly calculations
        yoy_quarterly_revenue = get_yoy_quarterly_growth(qf, "Total Revenue")
        yoy_quarterly_profit = get_yoy_quarterly_growth(qf, "Net Income")

        # Last quarter name
        if qf is not None and len(qf.columns) > 0:
            last_quarter_name = str(qf.columns[0].date())
        else:
            last_quarter_name = "NIL"

        # ---------------------------------------------------------------
        # 3️⃣ RESULT TABLE INITIALIZATION
        # ---------------------------------------------------------------
        result = [["Date"] + fields]

        # ---------------------------------------------------------------
        # 4️⃣ BUILD EACH ROW
        # ---------------------------------------------------------------
        for _, row in df.iterrows():
            entry = [row["Date"].strftime("%Y-%m-%d")]

            for field in fields:
                key = field.lower()

                # ----- DAILY RAW OHLCV -----
                if field in df.columns:
                    entry.append(safe_float(row[field]))
                    continue

                # ----- FAST INFO FIELDS (EXCEPT PRICES) -----
                # block price fields deliberately
                blocked_price_keys = ["last_price", "dayhigh", "daylow", "previousclose"]
                if key not in blocked_price_keys:
                    # Match case-insensitive keys
                    for k in fast_info.keys():
                        if k.lower() == key:
                            entry.append(safe_float(fast_info.get(k)))
                            break
                    else:
                        # continue checking other sources
                        pass

                # ----- INFO DICT FIELDS -----
                if key in map(str.lower, info.keys()):
                    matched = [k for k in info.keys() if k.lower() == key][0]
                    entry.append(info.get(matched, "NIL"))
                    continue

                # ----- CUSTOM CALCULATED FIELDS -----
                if key in ("52wh", "52weekhigh"):
                    entry.append(safe_float(fast_info.get("yearHigh", "NIL")))
                elif key in ("52wl", "52weeklow"):
                    entry.append(safe_float(fast_info.get("yearLow", "NIL")))
                elif key in ("mcap", "marketcap"):
                    entry.append(safe_float(fast_info.get("marketCap", info.get("marketCap", "NIL"))))
                elif key in ("pe", "p/e"):
                    entry.append(safe_float(fast_info.get("trailingPE", info.get("trailingPE", "NIL"))))
                elif key in ("sector",):
                    entry.append(info.get("sector", "NIL"))
                elif key in ("qoq_revenue_yoy", "yoy_quarterly_revenue"):
                    entry.append(yoy_quarterly_revenue)
                elif key in ("qoq_profit_yoy", "yoy_quarterly_profit"):
                    entry.append(yoy_quarterly_profit)
                elif key in ("last_quarter", "quarter_name"):
                    entry.append(last_quarter_name)
                else:
                    entry.append("NIL")

            result.append(entry)

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
