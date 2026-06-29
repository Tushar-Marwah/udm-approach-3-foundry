"""
BSE 100 + S&P 500 company entities (real names; illustrative synthetic financials,
deterministic from the name) -- seeded as the live `Company` object.
"""
import hashlib

# (name, ticker, sector)
SP500 = [
    ("Apple", "AAPL", "Technology"), ("Microsoft", "MSFT", "Technology"),
    ("Amazon", "AMZN", "Consumer Discretionary"), ("Nvidia", "NVDA", "Technology"),
    ("Alphabet", "GOOGL", "Communication Services"), ("Meta Platforms", "META", "Communication Services"),
    ("Berkshire Hathaway", "BRK.B", "Financials"), ("Tesla", "TSLA", "Consumer Discretionary"),
    ("JPMorgan Chase", "JPM", "Financials"), ("Visa", "V", "Financials"),
    ("Eli Lilly", "LLY", "Health Care"), ("UnitedHealth", "UNH", "Health Care"),
    ("Exxon Mobil", "XOM", "Energy"), ("Mastercard", "MA", "Financials"),
    ("Johnson & Johnson", "JNJ", "Health Care"), ("Procter & Gamble", "PG", "Consumer Staples"),
    ("Home Depot", "HD", "Consumer Discretionary"), ("Costco", "COST", "Consumer Staples"),
    ("Merck", "MRK", "Health Care"), ("AbbVie", "ABBV", "Health Care"),
    ("Chevron", "CVX", "Energy"), ("Coca-Cola", "KO", "Consumer Staples"),
    ("PepsiCo", "PEP", "Consumer Staples"), ("Broadcom", "AVGO", "Technology"),
    ("Adobe", "ADBE", "Technology"), ("Salesforce", "CRM", "Technology"),
    ("Netflix", "NFLX", "Communication Services"), ("Walmart", "WMT", "Consumer Staples"),
    ("Bank of America", "BAC", "Financials"), ("McDonald's", "MCD", "Consumer Discretionary"),
    ("Cisco", "CSCO", "Technology"), ("Pfizer", "PFE", "Health Care"),
    ("Accenture", "ACN", "Technology"), ("Thermo Fisher", "TMO", "Health Care"),
    ("Intel", "INTC", "Technology"), ("AMD", "AMD", "Technology"),
    ("Qualcomm", "QCOM", "Technology"), ("Texas Instruments", "TXN", "Technology"),
    ("Wells Fargo", "WFC", "Financials"), ("Goldman Sachs", "GS", "Financials"),
    ("Morgan Stanley", "MS", "Financials"), ("Boeing", "BA", "Industrials"),
    ("Caterpillar", "CAT", "Industrials"), ("Honeywell", "HON", "Industrials"),
    ("IBM", "IBM", "Technology"), ("Oracle", "ORCL", "Technology"),
    ("Nike", "NKE", "Consumer Discretionary"), ("Starbucks", "SBUX", "Consumer Discretionary"),
    ("Disney", "DIS", "Communication Services"), ("Verizon", "VZ", "Communication Services"),
    ("AT&T", "T", "Communication Services"), ("Comcast", "CMCSA", "Communication Services"),
    ("American Express", "AXP", "Financials"), ("BlackRock", "BLK", "Financials"),
    ("Lockheed Martin", "LMT", "Industrials"), ("General Electric", "GE", "Industrials"),
    ("3M", "MMM", "Industrials"), ("Ford", "F", "Consumer Discretionary"),
    ("General Motors", "GM", "Consumer Discretionary"), ("ConocoPhillips", "COP", "Energy"),
]

BSE100 = [
    ("Reliance Industries", "RELIANCE", "Energy"), ("Tata Consultancy Services", "TCS", "IT"),
    ("HDFC Bank", "HDFCBANK", "Financials"), ("Infosys", "INFY", "IT"),
    ("ICICI Bank", "ICICIBANK", "Financials"), ("Hindustan Unilever", "HINDUNILVR", "FMCG"),
    ("ITC", "ITC", "FMCG"), ("State Bank of India", "SBIN", "Financials"),
    ("Bharti Airtel", "BHARTIARTL", "Telecom"), ("Larsen & Toubro", "LT", "Industrials"),
    ("Kotak Mahindra Bank", "KOTAKBANK", "Financials"), ("Axis Bank", "AXISBANK", "Financials"),
    ("Bajaj Finance", "BAJFINANCE", "Financials"), ("Asian Paints", "ASIANPAINT", "Materials"),
    ("Maruti Suzuki", "MARUTI", "Auto"), ("HCL Technologies", "HCLTECH", "IT"),
    ("Sun Pharma", "SUNPHARMA", "Pharma"), ("Titan", "TITAN", "Consumer Discretionary"),
    ("Wipro", "WIPRO", "IT"), ("UltraTech Cement", "ULTRACEMCO", "Materials"),
    ("Nestle India", "NESTLEIND", "FMCG"), ("Tata Motors", "TATAMOTORS", "Auto"),
    ("NTPC", "NTPC", "Power"), ("Power Grid", "POWERGRID", "Power"),
    ("Mahindra & Mahindra", "M&M", "Auto"), ("Tech Mahindra", "TECHM", "IT"),
    ("JSW Steel", "JSWSTEEL", "Materials"), ("Tata Steel", "TATASTEEL", "Materials"),
    ("Adani Enterprises", "ADANIENT", "Industrials"), ("Adani Ports", "ADANIPORTS", "Industrials"),
    ("Coal India", "COALINDIA", "Energy"), ("Bajaj Auto", "BAJAJ-AUTO", "Auto"),
    ("Hindalco", "HINDALCO", "Materials"), ("Grasim", "GRASIM", "Materials"),
    ("Britannia", "BRITANNIA", "FMCG"), ("Dr Reddy's", "DRREDDY", "Pharma"),
    ("Cipla", "CIPLA", "Pharma"), ("Eicher Motors", "EICHERMOT", "Auto"),
    ("Divi's Labs", "DIVISLAB", "Pharma"), ("SBI Life", "SBILIFE", "Financials"),
    ("HDFC Life", "HDFCLIFE", "Financials"), ("Bajaj Finserv", "BAJAJFINSV", "Financials"),
    ("IndusInd Bank", "INDUSINDBK", "Financials"), ("ONGC", "ONGC", "Energy"),
    ("Hero MotoCorp", "HEROMOTOCO", "Auto"), ("Apollo Hospitals", "APOLLOHOSP", "Health Care"),
    ("Pidilite", "PIDILITIND", "Materials"), ("DMart (Avenue)", "DMART", "Retail"),
    ("Dabur", "DABUR", "FMCG"), ("Godrej Consumer", "GODREJCP", "FMCG"),
    ("Vedanta", "VEDL", "Materials"), ("Shree Cement", "SHREECEM", "Materials"),
    ("Bosch", "BOSCHLTD", "Auto"), ("Havells", "HAVELLS", "Industrials"),
    ("Marico", "MARICO", "FMCG"), ("Bank of Baroda", "BANKBARODA", "Financials"),
    ("Zomato", "ZOMATO", "Tech"), ("Paytm", "PAYTM", "Tech"),
    ("LIC", "LICI", "Financials"), ("DLF", "DLF", "Real Estate"),
]


def _h(*p):
    return int(hashlib.md5("|".join(str(x) for x in p).encode()).hexdigest(), 16)


def build_rows():
    """t_companies rows: company, ticker, idx, sector, country, mktcap, revenue,
    net_income, pe, div_yield, employees, gross_margin (synthetic, deterministic)."""
    rows = []
    for name, tick, sector in SP500:
        rows.append(_row(name, tick, "S&P 500", sector, "USA"))
    for name, tick, sector in BSE100:
        rows.append(_row(name, tick, "BSE 100", sector, "India"))
    return rows


def _row(name, tick, idx, sector, country):
    tier = _h(name) % 100
    mktcap = round(8000 + tier * tier * 2.2)          # USD mn, skewed so a few are huge
    rev = round(mktcap * (0.25 + (_h(name, "r") % 60) / 100.0))
    margin = round(18 + (_h(name, "m") % 45), 1)
    ni = round(rev * margin / 100.0 * (0.35 + (_h(name, "n") % 40) / 100.0))
    pe = round(8 + (_h(name, "p") % 55), 1)
    dy = round((_h(name, "d") % 45) / 10.0, 1)
    emp = 1500 + _h(name, "e") % 240000
    return (name, tick, idx, sector, country, mktcap, rev, ni, pe, dy, emp, margin)


COLS = ["company", "ticker", "idx", "sector", "country", "mktcap", "revenue",
        "net_income", "pe", "div_yield", "employees", "gross_margin"]

BINDINGS = [
    ("Company.name", "t_companies", "company", "-"),
    ("Company.ticker", "t_companies", "ticker", "-"),
    ("Company.index", "t_companies", "idx", "-"),
    ("Company.sector", "t_companies", "sector", "-"),
    ("Company.country", "t_companies", "country", "-"),
    ("Company.market_cap_mn", "t_companies", "mktcap", "-"),
    ("Company.revenue_mn", "t_companies", "revenue", "-"),
    ("Company.net_income_mn", "t_companies", "net_income", "-"),
    ("Company.pe", "t_companies", "pe", "-"),
    ("Company.dividend_yield", "t_companies", "div_yield", "-"),
    ("Company.employees", "t_companies", "employees", "to_int"),
    ("Company.gross_margin", "t_companies", "gross_margin", "-"),
]
