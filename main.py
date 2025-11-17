import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Utility: simple symbol -> coingecko id map ---
SYMBOL_MAP = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "USDT": "tether",
    "SOL": "solana",
    "BNB": "binancecoin",
    "XRP": "ripple",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "MATIC": "matic-network",
    "DOT": "polkadot",
    "LTC": "litecoin",
}

SUPPORTED_FIATS = {"USD", "EUR", "GBP", "JPY", "AUD", "CAD", "INR"}


class ConvertRequest(BaseModel):
    amount: float = Field(gt=0)
    fiat: str = Field(description="Fiat currency code, e.g., USD")
    symbol: str = Field(description="Crypto symbol, e.g., BTC")


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/api/price")
def get_price(symbol: str = "BTC", fiat: str = "USD"):
    symbol = symbol.upper()
    fiat = fiat.upper()
    if fiat not in SUPPORTED_FIATS:
        raise HTTPException(status_code=400, detail=f"Unsupported fiat '{fiat}'. Supported: {sorted(SUPPORTED_FIATS)}")
    if symbol not in SYMBOL_MAP:
        raise HTTPException(status_code=400, detail=f"Unsupported symbol '{symbol}'. Supported: {sorted(SYMBOL_MAP.keys())}")

    cg_id = SYMBOL_MAP[symbol]
    url = f"https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": cg_id, "vs_currencies": fiat.lower()}
    try:
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        data = r.json()
        price = data.get(cg_id, {}).get(fiat.lower())
        if price is None:
            raise HTTPException(status_code=502, detail="Price not available from provider")
        return {"symbol": symbol, "fiat": fiat, "price": float(price)}
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Price provider error: {str(exc)[:120]}")


@app.post("/api/convert")
def convert(req: ConvertRequest):
    price_resp = get_price(req.symbol, req.fiat)
    converted = req.amount / price_resp["price"] if price_resp["price"] > 0 else 0.0
    return {
        "amount": req.amount,
        "fiat": price_resp["fiat"],
        "symbol": price_resp["symbol"],
        "price": price_resp["price"],
        "converted": converted,
    }


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        # Try to import database module
        from database import db
        
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            # Try to list collections to verify connectivity
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    # Check environment variables
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
