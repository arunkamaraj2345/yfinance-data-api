from flask import Flask, request, jsonify
import yfinance as yf
from datetime import datetime

app = Flask(__name__)

@app.route('/get_stock_data_between_dates', methods=['GET'])
def get_stock_data_between_dates():
    symbol = request.args.get('symbol')
    start = request.args.get('start')
    end = request.args.get('end')

    extra_fields = request.args.get('fields')
    if extra_fields:
        # 🚀 KEEP EXACT CASE — no lowercasing
        fields = [f.strip() for f in extra_fields.split(",")]
    else:
        fields = ["Close"]

    if not symbol or not start or not end:
        return jsonify({"error": "Missing parameters: symbol, start, end"})

    try:
        ticker = yf.Ticker(symbol)

        # 🚀 Always split-adjusted Close only (consistent with your requirement)
        df = ticker.history(start=start, end=end, auto_adjust=False).reset_index()

        if df.empty:
            return jsonify({"error": f"No data found for {symbol} between {start} and {end}."})

        if "Date" in df.columns:
            df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

        # Grab info dictionary only once
        info = ticker.info

        result = [["Date"] + fields]

        for _, row in df.iterrows():
            entry = [row["Date"]]

            for field in fields:

                # 1️⃣ OHLCV (exact case)
                if field in df.columns:
                    entry.append(float(row[field]))
                    continue

                # 2️⃣ Old script compatibility
                if field.lower() == "52weekhigh":
                    entry.append(float(ticker.fast_info.get("yearHigh", "NIL")))
                    continue

                if field.lower() == "52weeklow":
                    entry.append(float(ticker.fast_info.get("yearLow", "NIL")))
                    continue

                # 3️⃣ Extra Info Fields (ONLY if explicitly requested)
                value = info.get(field, "NIL")

                if isinstance(value, (int, float)):
                    entry.append(value)
                else:
                    entry.append("NIL")

            result.append(entry)

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)})


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
