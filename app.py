from flask import Flask, request, jsonify
import yfinance as yf
import pandas as pd

app = Flask(__name__)


def safe_float(val):
    try:
        return float(val)
    except:
        return "NIL"


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
        # 1️⃣ PRICE DATA — strict rule: auto_adjust=False
        # ---------------------------------------------------------------
        df = ticker.history(start=start, end=end, auto_adjust=False).reset_index()

        if df.empty:
            return jsonify({"error": f"No data found for {symbol}."})

        # ---------------------------------------------------------------
        # 2️⃣ FAST INFO + INFO (for metadata)
        # ---------------------------------------------------------------
        fast_info = ticker.fast_info or {}
        info = ticker.info or {}

        # ---------------------------------------------------------------
        # 3️⃣ RESULT HEADER
        # ---------------------------------------------------------------
        result = [["Date"] + fields]

        # ---------------------------------------------------------------
        # 4️⃣ BUILD EACH ROW
        # ---------------------------------------------------------------
        for _, row in df.iterrows():
            entry = [row["Date"].strftime("%Y-%m-%d")]

            for field in fields:
                key = field.lower()

                # ----- DAILY OHLCV (from history) -----
                if field in df.columns:
                    entry.append(safe_float(row[field]))
                    continue

                # ----- FAST INFO (but NEVER prices) -----
                blocked_prices = ["last_price", "previousclose", "daylow", "dayhigh"]
                if key not in blocked_prices:
                    for k in fast_info.keys():
                        if k.lower() == key:
                            entry.append(safe_float(fast_info.get(k)))
                            break
                    else:
                        pass

                # ----- INFO DICTIONARY (includes growth %) -----
                if key in map(str.lower, info.keys()):
                    actual_key = [k for k in info.keys() if k.lower() == key][0]
                    entry.append(info.get(actual_key, "NIL"))
                    continue

                # ----- CUSTOM SHORTCUTS -----
                if key in ("52wh", "52weekhigh"):
                    entry.append(safe_float(fast_info.get("yearHigh", info.get("fiftyTwoWeekHigh", "NIL"))))
                elif key in ("52wl", "52weeklow"):
                    entry.append(safe_float(fast_info.get("yearLow", info.get("fiftyTwoWeekLow", "NIL"))))
                elif key in ("mcap", "marketcap"):
                    entry.append(safe_float(fast_info.get("marketCap", info.get("marketCap", "NIL"))))
                elif key in ("pe", "p/e"):
                    entry.append(safe_float(fast_info.get("trailingPE", info.get("trailingPE", "NIL"))))
                elif key in ("earningsquarterlygrowth", "earn_q_growth"):
                    entry.append(
                        safe_float(info.get("earningsQuarterlyGrowth", "NIL"))
                    )
                elif key in ("revenuequarterlygrowth", "rev_q_growth"):
                    entry.append(
                        safe_float(info.get("revenueQuarterlyGrowth", "NIL"))
                    )
                else:
                    entry.append("NIL")

            result.append(entry)

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
