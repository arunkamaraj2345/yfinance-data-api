from flask import Flask, request, jsonify
import yfinance as yf

app = Flask(__name__)

@app.route('/get_stock_data_between_dates', methods=['GET'])
def get_stock_data_between_dates():

    symbol = request.args.get("symbol")
    start = request.args.get("start")
    end = request.args.get("end")

    extra_fields = request.args.get("fields")
    if extra_fields:
        fields = [f.strip() for f in extra_fields.split(",")]
    else:
        fields = ["Close"]

    if not symbol or not start or not end:
        return jsonify({"error": "Missing parameters: symbol, start, end"})

    try:
        ticker = yf.Ticker(symbol)

        df = ticker.history(start=start, end=end, auto_adjust=False).reset_index()
        if df.empty:
            return jsonify({"error": f"No data found for {symbol} between {start} and {end}."})

        # Ensure Date column formatted correctly
        if "Date" in df.columns:
            df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

        # Prepare output header
        result = [["Date"] + fields]

        # Fetch info & fast_info ONCE
        info = ticker.info or {}
        fast = ticker.fast_info or {}

        # Build rows
        for _, row in df.iterrows():
            entry = [row["Date"]]

            for field in fields:
                f = field.lower()

                # --- OHLCV from dataframe ---
                if field in df.columns:
                    entry.append(float(row[field]))
                    continue

                # --- 52w high/low ---
                if f == "52weekhigh":
                    entry.append(float(fast.get("yearHigh", "NIL")))
                    continue

                if f == "52weeklow":
                    entry.append(float(fast.get("yearLow", "NIL")))
                    continue

                # --- info-based fields ---
                if f == "marketcap":
                    entry.append(info.get("marketCap", "NIL"))
                    continue

                if f in ("trailingpe", "p/e", "pe"):
                    entry.append(info.get("trailingPE", "NIL"))
                    continue

                if f == "earningsquarterlygrowth":
                    entry.append(info.get("earningsQuarterlyGrowth", "NIL"))
                    continue

                if f == "revenuequarterlygrowth":
                    entry.append(info.get("revenueQuarterlyGrowth", "NIL"))
                    continue

                # Unknown field fallback
                entry.append("NIL")

            result.append(entry)

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
