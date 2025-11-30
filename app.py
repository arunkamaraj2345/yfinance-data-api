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
        fields = [f.strip() for f in extra_fields.split(",")]   # ❗ No capitalize()
    else:
        fields = ["Close"]

    if not symbol or not start or not end:
        return jsonify({"error": "Missing parameters: symbol, start, end"})

    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start, end=end, auto_adjust=False).reset_index()

        if df.empty:
            return jsonify({"error": f"No data found for {symbol} between {start} and {end}."})

        # Preload info + fast_info ONCE
        info = ticker.info
        fast_info = ticker.fast_info

        # convert date to string
        if "Date" in df.columns:
            df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

        result = [["Date"] + fields]

        for _, row in df.iterrows():
            entry = [row["Date"]]

            for field in fields:

                # 1️⃣ df (OHLCV price data)
                if field in df.columns:
                    entry.append(float(row[field]))
                    continue

                # 2️⃣ special 52-week compatibility
                if field.lower() == "52weekhigh":
                    entry.append(float(fast_info.get("yearHigh")) if fast_info.get("yearHigh") else None)
                    continue

                if field.lower() == "52weeklow":
                    entry.append(float(fast_info.get("yearLow")) if fast_info.get("yearLow") else None)
                    continue

                # 3️⃣ direct .info fields (marketCap, trailingPE, growth data)
                if field in info:
                    val = info[field]
                    entry.append(float(val) if isinstance(val, (float, int)) else None)
                    continue

                # 4️⃣ direct fast_info fields (only if explicitly named)
                if field in fast_info:
                    val = fast_info[field]
                    entry.append(float(val) if isinstance(val, (float, int)) else None)
                    continue

                # 5️⃣ unknown field
                entry.append(None)

            result.append(entry)

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}})


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
