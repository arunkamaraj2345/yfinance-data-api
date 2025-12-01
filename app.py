from flask import Flask, request, jsonify
import yfinance as yf
from datetime import datetime, timedelta

app = Flask(__name__)

@app.route('/get_stock_data_between_dates', methods=['GET'])
def get_stock_data_between_dates():
    symbol = request.args.get('symbol')
    start = request.args.get('start')
    end = request.args.get('end')

    extra_fields = request.args.get('fields')
    if extra_fields:
        # ❌ Was f.strip().capitalize() — destroyed camelCase like marketCap
        # ✅ Keep the field EXACTLY as user passes it
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

        # Ensure Date column always in YYYY-MM-DD format
        if "Date" in df.columns:
            df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

        fast_info = ticker.fast_info

        result = [["Date"] + fields]

        for _, row in df.iterrows():
            entry = [row["Date"]]  # already a string in YYYY-MM-DD

            for field in fields:

                # 1️⃣ Direct match from DF columns (Close, Open, High, etc.)
                if field in df.columns:
                    entry.append(float(row[field]))
                    continue

                # 2️⃣ 52-week high
                if field.lower() == "52weekhigh":
                    entry.append(float(fast_info.get("yearHigh", "NIL")))
                    continue

                # 3️⃣ 52-week low
                if field.lower() == "52weeklow":
                    entry.append(float(fast_info.get("yearLow", "NIL")))
                    continue

                # 4️⃣ Market Cap (case-sensitive "marketCap")
                if field == "marketCap":
                    entry.append(float(fast_info.get("marketCap", "NIL")))
                    continue

                # 5️⃣ Anything unknown → NIL
                entry.append("NIL")

            result.append(entry)

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)})


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
