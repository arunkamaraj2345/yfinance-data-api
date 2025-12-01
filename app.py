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

    # Normalize field names (used for price fields)
    normalized_fields = [f.capitalize() for f in fields]

    if not symbol or not start or not end:
        return jsonify({"error": "Missing parameters: symbol, start, end"})

    try:
        ticker = yf.Ticker(symbol)

        # Load only if user requested new info fields → performance optimization
        info_fields_requested = any(
            f.lower() in [
                "marketcap", 
                "trailingpe", 
                "earningsquarterlygrowth", 
                "revenuequarterlygrowth"
            ] 
            for f in fields
        )

        info_data = {}
        if info_fields_requested:
            try:
                info_data = ticker.info  # Loaded only on demand
            except Exception:
                info_data = {}

        df = ticker.history(start=start, end=end, auto_adjust=False).reset_index()

        if df.empty:
            return jsonify({"error": f"No data found for {symbol} between {start} and {end}."})

        # Ensure Date is formatted correctly
        if "Date" in df.columns:
            df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

        result = [["Date"] + fields]

        for _, row in df.iterrows():
            entry = [row["Date"]]

            for original_field in fields:
                field = original_field.lower()

                # Handle normal OHLCV fields (Open, Close, etc.)
                if original_field.capitalize() in df.columns:
                    entry.append(float(row[original_field.capitalize()]))
                
                # Existing special fields
                elif field == "52weekhigh":
                    entry.append(float(ticker.fast_info.get("yearHigh", "NIL")))
                
                elif field == "52weeklow":
                    entry.append(float(ticker.fast_info.get("yearLow", "NIL")))

                # New OPTIONAL fields from info() — loaded only when requested
                elif field == "marketcap":
                    entry.append(info_data.get("marketCap", "NIL"))

                elif field == "trailingpe":
                    entry.append(info_data.get("trailingPE", "NIL"))

                elif field == "earningsquarterlygrowth":
                    entry.append(info_data.get("earningsQuarterlyGrowth", "NIL"))

                elif field == "revenuequarterlygrowth":
                    entry.append(info_data.get("revenueQuarterlyGrowth", "NIL"))

                # If unknown field
                else:
                    entry.append("NIL")

            result.append(entry)

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)})


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
