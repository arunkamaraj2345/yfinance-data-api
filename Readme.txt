============================================================
STOCK DATA API (Flask + yfinance)
============================================================

1. OVERVIEW
------------------------------------------------------------
This is a REST API built using Flask and yfinance.

It allows users to:
- Fetch historical stock data between custom dates
- Request specific fields like OHLC, Volume
- Retrieve 52 Week High
- Retrieve 52 Week Low
- Retrieve Market Capitalization

The API is deployed on Render and can be accessed via HTTP GET requests.


2. TECH STACK
------------------------------------------------------------
- Python 3.x
- Flask
- yfinance
- Gunicorn (for production)
- Render (deployment)


3. PROJECT STRUCTURE
------------------------------------------------------------
project/
│
├── app.py
├── requirements.txt
├── README.txt


4. LOCAL INSTALLATION
------------------------------------------------------------

STEP 1: Clone the Repository

git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name


STEP 2: Create Virtual Environment (Recommended)

python -m venv venv

Activate it:

Windows:
venv\Scripts\activate

Mac/Linux:
source venv/bin/activate


STEP 3: Create requirements.txt with:

flask
yfinance
gunicorn


STEP 4: Install Dependencies

pip install -r requirements.txt


STEP 5: Run the Server

python app.py

Server will start at:
http://127.0.0.1:8080


5. RENDER DEPLOYMENT SETTINGS
------------------------------------------------------------

Start Command:
gunicorn app:app

Environment:
Python 3

Render automatically assigns PORT.


6. API ENDPOINTS
============================================================

------------------------------------------------------------
1) SERVER STATUS ENDPOINT
------------------------------------------------------------

URL:
GET /status

Purpose:
- Warms up Yahoo Finance connection
- Calls history()
- Calls fast_info
- Stabilizes connection pool

Example:
https://your-render-url.onrender.com/status

Success Response:
{
  "status": "server on",
  "warmup status": "server warm",
  "time": "YYYY-MM-DD HH:MM:SS"
}

Failure Response:
{
  "status": "server on",
  "warmup status": "warmup failed",
  "error": "Error message"
}


------------------------------------------------------------
2) GET STOCK DATA BETWEEN DATES
------------------------------------------------------------

URL:
GET /get_stock_data_between_dates

Required Parameters:

symbol   = Stock symbol (Example: RELIANCE.NS)
start    = Start date (YYYY-MM-DD)
end      = End date (YYYY-MM-DD)

Optional Parameter:

fields   = Comma-separated list of fields


7. SUPPORTED FIELDS
------------------------------------------------------------

From Historical Data:
Open
High
Low
Close
Volume
Dividends
Stock Splits

From fast_info:
52weekhigh
52weeklow
marketCap

If fields parameter is NOT provided:
Default field = Close


8. EXAMPLE API CALLS
------------------------------------------------------------

Example 1: Close Price Only

/get_stock_data_between_dates?symbol=RELIANCE.NS&start=2024-01-01&end=2024-02-01


Example 2: OHLC Data

/get_stock_data_between_dates?symbol=RELIANCE.NS&start=2024-01-01&end=2024-02-01&fields=Open,High,Low,Close


Example 3: Include 52 Week High & Market Cap

/get_stock_data_between_dates?symbol=RELIANCE.NS&start=2024-01-01&end=2024-02-01&fields=Close,52weekhigh,marketCap


9. RESPONSE FORMAT
------------------------------------------------------------

The API returns a JSON array structured like this:

[
  ["Date", "Field1", "Field2"],
  ["2024-01-01", value1, value2],
  ["2024-01-02", value1, value2]
]

This format is spreadsheet-friendly and can be used in:
- Google Sheets
- Excel
- Python scripts
- Trading systems


10. ERROR HANDLING
------------------------------------------------------------

Missing Parameters:
{
  "error": "Missing parameters: symbol, start, end"
}

No Data Found:
{
  "error": "No data found for SYMBOL between START and END."
}

Internal Error:
{
  "error": "Error message"
}


11. IMPORTANT NOTES
------------------------------------------------------------

- Data is fetched from Yahoo Finance using yfinance.
- 52 Week High/Low and Market Cap come from fast_info.
- fast_info values remain constant for all returned dates.
- Yahoo Finance rate limits may apply.
- NSE symbols must include ".NS" suffix.


12. EXAMPLE NSE SYMBOLS
------------------------------------------------------------

RELIANCE.NS
TCS.NS
INFY.NS
HDFCBANK.NS


13. FUTURE IMPROVEMENTS (OPTIONAL)
------------------------------------------------------------

- Add API key authentication
- Add rate limiting
- Add caching (Redis)
- Add SMA/EMA endpoint
- Add market breadth endpoint
- Add CSV output option


14. LICENSE
------------------------------------------------------------

Use at your own discretion.
Data Source: Yahoo Finance (via yfinance).

============================================================
END OF FILE
============================================================