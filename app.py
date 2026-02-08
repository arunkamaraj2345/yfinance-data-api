from flask import Flask, request, jsonify
import yfinance as yf
import time
from datetime import datetime, timedelta

app = Flask(__name__)

# ============================
# SERVER STATUS ENDPOINT
# ============================
@app.route('/status', methods=['GET'])
def status():
    try:
        print("=== SERVER WARMUP START ===")

        ticker = yf.Ticker("RELIANCE.NS")

        # Warm price endpoint
        ticker.history(period="5d")

        # Warm fast_info endpoint (used in your API)
        _ = ticker.fast_info
        _ = ticker.info

        # Stabilize connection pool
        time.sleep(2)

        print("=== SERVER WARMUP COMPLETE ===")

        return jsonify({
            "status" : "server on",
            "warmup status": "server warm",
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    except Exception as e:
        return jsonify({
            "status" : "server on",
            "warmup status": "warmup failed",
            "error": str(e)
        }), 500


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

    if not symbol or not start or not end:
        return jsonify({"error": "Missing parameters: symbol, start, end"})

    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start, end=end, auto_adjust=False).reset_index()

        if df.empty:
            return jsonify({"error": f"No data found for {symbol} between {start} and {end}."})

        if "Date" in df.columns:
            df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

        fast_info = ticker.fast_info

        result = [["Date"] + fields]

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

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)})


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)


