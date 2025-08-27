from flask import Flask, request, jsonify
import yfinance as yf

app = Flask(__name__)

@app.route('/get_stock_data_between_dates', methods=['GET'])
def get_stock_data_between_dates():
    symbol = request.args.get('symbol')
    start = request.args.get('start')
    end = request.args.get('end')

    # Optional fields requested by user
    extra_fields = request.args.get('fields')  # e.g. fields=Close,Volume,Open
    if extra_fields:
        fields = [f.strip().capitalize() for f in extra_fields.split(",")]
    else:
        fields = ["Close"]  # default → only Close

    if not symbol or not start or not end:
        return jsonify({"error": "Missing parameters: symbol, start, end"})

    try:
        # Fetch OHLCV data with split-adjusted close only
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start, end=end, auto_adjust=False).reset_index()

        if df.empty:
            return jsonify({"error": f"No data found for {symbol} between {start} and {end}."})

        result = [["Date"] + fields]

        # Build rows
        for _, row in df.iterrows():
            entry = [row['Date'].strftime('%Y-%m-%d')]
            for field in fields:
                if field in df.columns:
                    entry.append(float(row[field]))
                elif field.lower() == "52weekhigh":
                    entry.append(float(ticker.fast_info.get("yearHigh", "N/A")))
                elif field.lower() == "52weeklow":
                    entry.append(float(ticker.fast_info.get("yearLow", "N/A")))
                else:
                    entry.append("NIL")  # fallback if invalid field
            result.append(entry)

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
