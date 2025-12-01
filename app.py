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
        fields = [f.strip() for f in extra_fields.split(",")]
    else:
        fields = ["Close"]

    # Basic parameter validation
    if not symbol or not start or not end:
        return jsonify({"error": "Missing parameters: symbol, start, end"})

    try:
        ticker = yf.Ticker(symbol)

        # Fetch historical OHLCV data
        df = ticker.history(start=start, end=end, auto_adjust=False).reset_index()

        if df.empty:
            return jsonify({"error": f"No data found for {symbol} between {start} and {end}."})

        # Date formatting
        if "Date" in df.columns:
            df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

        # Build output table header
        result = [["Date"] + fields]

        # Iterate through each row in history
        for _, row in df.iterrows():
            entry = [row["Date"]]

            for field in fields:

                # 1️⃣ Direct OHLCV columns (Close, Open, High, Low, Volume)
                if field in df.columns:
                    entry.append(float(row[field]))
                    continue

                # 2️⃣ Old fields — case-insensitive (backward compatibility)
                if field.lower() == "52weekhigh":
                    entry.append(float(ticker.fast_info.get("yearHigh", "NIL")))
                    continue

                if field.lower() == "52weeklow":
                    entry.append(float(ticker.fast_info.get("yearLow", "NIL")))
                    continue

                # 3️⃣ New fields — EXACT MATCH (case-sensitive)
                if field == "marketCap":
                    entry.append(ticker.fast_info.get("market_cap", "NIL"))
                    continue

                if field == "trailingPE":
                    entry.append(ticker.info.get("trailingPE", "NIL"))
                    continue

                if field == "earningsQuarterlyGrowth":
                    entry.append(ticker.info.get("earningsQuarterlyGrowth", "NIL"))
                    continue

                if field == "revenueQuarterlyGrowth":
                    entry.append(ticker.info.get("revenueQuarterlyGrowth", "NIL"))
                    continue

                # 4️⃣ Unknown field
                entry.append("NIL")

            result.append(entry)

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)})


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
