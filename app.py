from flask import Flask, request, jsonify
import yfinance as yf

app = Flask(__name__)

@app.route('/get_stock_data_between_dates', methods=['GET'])
def get_stock_data_between_dates():
    symbol = request.args.get('symbol')
    start = request.args.get('start')
    end = request.args.get('end')

    # Fields requested by script
    extra_fields_raw = request.args.get('fields')
    if extra_fields_raw:
        fields = [f.strip() for f in extra_fields_raw.split(',')]
    else:
        fields = ["Close"]   # default behavior

    if not symbol or not start or not end:
        return jsonify({"error": "Missing symbol/start/end"})

    try:
        # Fetch OHLCV (auto_adjust=False for split-corrected only)
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start, end=end, auto_adjust=False)

        if df.empty:
            return jsonify({"error": f"No data found for {symbol}."})

        df = df.reset_index()

        # Fast info and slow info
        fast_info = {}
        try:
            fast_info = ticker.fast_info.__dict__ if hasattr(ticker, "fast_info") else ticker.fast_info
        except:
            fast_info = {}

        info = {}
        try:
            info = ticker.info
        except:
            info = {}

        # ------------------------------------
        # BUILD HEADER ROW
        # ------------------------------------

        header = ["Date"] + fields
        result = [header]

        # ------------------------------------
        # BUILD DATA ROWS
        # ------------------------------------

        for _, row in df.iterrows():
            entry = [row["Date"].strftime("%Y-%m-%d")]

            for field in fields:
                key = field.lower()

                # 1 — FIRST: price fields from df
                if key in ["open", "high", "low", "close", "volume"]:
                    if field.capitalize() in df.columns:
                        entry.append(float(row[field.capitalize()]))
                    else:
                        entry.append(None)
                    continue

                # 2 — SECOND: fast_info values
                if key in fast_info:
                    val = fast_info[key]
                    if isinstance(val, (int, float)):
                        entry.append(val)
                    else:
                        entry.append(None)
                    continue

                # 3 — THIRD: info dict values
                if key in info:
                    val = info[key]
                    if isinstance(val, (int, float)):
                        entry.append(val)
                    else:
                        entry.append(None)
                    continue

                # 4 — fallback
                entry.append(None)

            result.append(entry)

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)})


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
