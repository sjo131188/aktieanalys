print("--- SKRIPTET HAR STARTAT ---")

import os
import requests
import yfinance as yf
from supabase import create_client, Client
from dotenv import load_dotenv  # <--- LÄGG TILL DENNA RAD

# Ladda in variabler från .env-filen
load_dotenv() # <--- LÄGG TILL DENNA RAD

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
    print("--- Startar synkronisering ---")
    tickers = get_portfolio_tickers()
    print(f"Hittade tickers i databasen: {tickers}")
    
    if not tickers:
        print("Inga aktier att bearbeta. Avslutar.")
        return

    for ticker in tickers:
        print(f"\nHämtar data för: {ticker}...")
        stock = yf.Ticker(ticker)
        
        try:
            news_list = stock.news
            if not news_list:
                print(f"Inga nyheter hittades för {ticker} just nu.")
                continue
            
            print(f"Hittade {len(news_list)} råa nyhetsobjekt. Bearbetar...")
            
            for news in news_list[:5]:
                # 1. Packa upp 'content' om det finns (Yahoos nya format)
                details = news.get('content', news) 
            
                # 2. Hämta fälten från 'details' istället
                title = details.get('title')
                link = details.get('clickThroughUrl', {}).get('url') or details.get('canonicalUrl', {}).get('url')
                publisher = details.get('provider', {}).get('displayName', 'Okänd källa')
            
            # DEBUG: Se vad vi hittar nu
                if not title or not link:
                    print(f"Skippar: Saknar titel eller länk. (Titel: {title})")
                    continue
            
                # 3. Kolla dubbletter i Supabase
                exists = supabase.table("news_items").select("id").eq("url", link).execute()
                if exists.data:
                    print(f"Redan sparad: {title[:40]}...")
                    continue
            
                print(f"Analyserar sentiment för: {title[:50]}...")
            
                # 4. Analysera med din AI
                analysis = analyze_text(title)
                sentiment = analysis['sentiment'] if analysis else "neutral"
                score = analysis['confidence'] if analysis else 0.0
            
                # 5. Spara i Supabase
                data = {
                    "title": title,
                    "url": link,
                    "source": publisher,
                    "sentiment": sentiment,
                    "sentiment_score": score,
                    "matched_symbols": [ticker]
                }
            
                try:
                    supabase.table("news_items").insert(data).execute()
                    print(f"✅ SPARAD: [{sentiment}] {title[:30]}...")
                except Exception as e:
                    print(f"❌ Kunde inte spara: {e}")

        except Exception as e:
            print(f"❌ Fel vid bearbetning av {ticker}: {e}")

    print("\n--- Synkronisering klar! ---")
if __name__ == "__main__":
    run_sync()