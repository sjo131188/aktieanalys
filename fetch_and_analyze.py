import os
import requests
import yfinance as yf
from supabase import create_client, Client

# --- KONFIGURATION ---
# 1. Supabase URL
# Först letar vi efter miljövariabeln "SUPABASE_URL". Om den inte finns, används din länk.
SUPABASE_URL = os.environ.get("SUPABASE_URL")

# 2. Supabase Service Key
# Här letar vi efter "SUPABASE_SERVICE_ROLE_KEY". Om den inte finns, används din nyckel.
# (Klistra in din riktiga långa nyckel mellan de sista citattechnerna)
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

# 3. Hugging Face API
# Denna URL är fast och pekar direkt på din AI-motor.
HF_API_URL = "https://sjo131188-min-aktie-analys.hf.space/analyze"
# Initiera Supabase-klienten
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_portfolio_tickers():
    """Hämtar alla unika tickers som användare har i sina portföljer."""
    response = supabase.table("holdings").select("ticker").eq("active", True).execute()
    # Skapa ett set av unika tickers för att slippa dubbla anrop
    return list(set([item['ticker'] for item in response.data]))

def analyze_text(text):
    """Skickar text till din Hugging Face Space för FinBERT-analys."""
    try:
        # Väck HF Space om den sover (timeout=30)
        response = requests.post(HF_API_URL, json={"text": text}, timeout=30)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"AI-Analys misslyckades: {e}")
    return None

def run_sync():
    print("Startar hämtning av nyheter...")
    tickers = get_portfolio_tickers()
    
    if not tickers:
        print("Inga aktier hittades i databasen.")
        return

    for ticker in tickers:
        print(f"Bearbetar {ticker}...")
        stock = yf.Ticker(ticker)
        news_list = stock.news
        
        for news in news_list[:5]: # De 5 senaste nyheterna per aktie
            title = news.get('title')
            link = news.get('link')
            publisher = news.get('publisher')
            
            # 1. Kolla om nyheten redan finns (undvik dubbletter)
            exists = supabase.table("news_items").select("id").eq("url", link).execute()
            if exists.data:
                continue
            
            # 2. Analysera med FinBERT
            analysis = analyze_text(title)
            sentiment = analysis['sentiment'] if analysis else "neutral"
            score = analysis['confidence'] if analysis else 0.0
            
            # 3. Spara i news_items
            data = {
                "title": title,
                "url": link,
                "source": publisher,
                "sentiment": sentiment,
                "sentiment_score": score,
                "matched_symbols": [ticker]
            }
            
            result = supabase.table("news_items").insert(data).execute()
            print(f"Sparad nyhet: {title} [{sentiment}]")

if __name__ == "__main__":
    run_sync()