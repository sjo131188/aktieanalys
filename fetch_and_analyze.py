print("--- SKRIPTET HAR STARTAT ---")

import os
import requests
import yfinance as yf
from supabase import create_client, Client

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("DEBUG: python-dotenv ej installerad, använder systemets miljövariabler.")

# --- KONFIGURATION ---
# 1. Supabase URL
# Först letar vi efter miljövariabeln "SUPABASE_URL". Om den inte finns, används din länk.
SUPABASE_URL = os.environ.get("SUPABASE_URL")

# 2. Supabase Service Key
# Här letar vi efter "SUPABASE_SERVICE_ROLE_KEY". Om den inte finns, används din nyckel.
# (Klistra in din riktiga långa nyckel mellan de sista citattechnerna)
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")


# Initiera Supabase-klienten
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_portfolio_tickers():
    """Hämtar alla unika tickers som användare har i sina portföljer."""
    response = supabase.table("holdings").select("ticker").eq("active", True).execute()
    # Skapa ett set av unika tickers för att slippa dubbla anrop
    return list(set([item['ticker'] for item in response.data]))

import requests

HF_TOKEN = os.getenv("HF_TOKEN")
# Den nya adressen som Hugging Face kräver:
API_URL = "https://router.huggingface.co/hf-inference/models/ProsusAI/finbert"
headers = {"Authorization": f"Bearer {HF_TOKEN}"}

def analyze_text(text):
    if not HF_TOKEN:
        print("❌ FEL: HF_TOKEN saknas i miljön!")
        return None
        
    try:
        response = requests.post(API_URL, headers=headers, json={"inputs": text}, timeout=20)
        
        # Om modellen håller på att laddas, vänta och försök igen en gång
        if response.status_code == 503:
            print("⏳ Modellen laddas på Hugging Face, väntar 10 sekunder...")
            import time
            time.sleep(10)
            response = requests.post(API_URL, headers=headers, json={"inputs": text}, timeout=20)

        if response.status_code == 200:
            raw_result = response.json()
            # API:et returnerar ibland [[{...}]]
            if isinstance(raw_result, list) and len(raw_result) > 0:
                inner = raw_result[0]
                result = inner[0] if isinstance(inner, list) else inner
                return {
                    "sentiment": result['label'],
                    "confidence": result['score']
                }
        else:
            print(f"❌ API-fel: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ Systemfel vid analys: {e}")
    return None

def run_sync():
    print("--- Startar synkronisering ---")
    tickers = get_portfolio_tickers()
    print(f"Hittade tickers: {tickers}")
    
    for ticker in tickers:
        try:
            print(f"\n--- Bearbetar {ticker} ---")
            stock = yf.Ticker(ticker)
            news_list = stock.news
            
            if not news_list:
                print(f"⚠️ Inga nyheter alls hittades för {ticker} via Yahoo Finance.")
                continue

            # Nollställ statistik för varje ny aktie
            stats = {"positive": 0, "negative": 0, "neutral": 0}
            processed_count = 0
            
            print(f"Hittade {len(news_list)} råa nyheter. Analyserar de 5 senaste...")

            for news in news_list[:5]:
                details = news.get('content', news)
                title = details.get('title')
                
                # Säkra länken
                link_obj = details.get('clickThroughUrl') or details.get('canonicalUrl') or {}
                link = link_obj.get('url') if isinstance(link_obj, dict) else None

                if not title or not link:
                    continue

                # KOLLA SUPABASE
                exists = supabase.table("news_items").select("id").eq("url", link).execute()
                
                if exists.data:
                    print(f"  - Redan sparad: {title[:40]}...")
                    # VALFRITT: Om du vill räkna statistik även på gamla, gör det här
                    continue

                # ANALYSERA NYA
                print(f"  - Analyserar ny artikel: {title[:40]}...")
                analysis = analyze_text(title)
                
                if analysis:
                    sentiment = analysis['sentiment'].lower()
                    score = analysis['confidence']
                    stats[sentiment] += 1
                    processed_count += 1
                    
                    # Spara i databasen
                    data = {
                        "title": title, "url": link, "sentiment": sentiment,
                        "sentiment_score": score, "matched_symbols": [ticker]
                    }
                    supabase.table("news_items").insert(data).execute()

            # --- SAMMANFATTNING ---
            # Denna print MÅSTE ligga kvar i ticker-loopen men utanför news-loopen
            if processed_count > 0:
                print(f"\n📊 RESULTAT FÖR {ticker}:")
                print(f"   Antal analyserade nu: {processed_count}")
                print(f"   Positiva: {stats['positive']} | Negativa: {stats['negative']} | Neutrala: {stats['neutral']}")
                
                if stats['positive'] > stats['negative']:
                    print(f"   🚀 Bedömning: BULLISH")
                elif stats['negative'] > stats['positive']:
                    print(f"   ⚠️ Bedömning: BEARISH")
                else:
                    print(f"   ⚖️ Bedömning: NEUTRAL")
            else:
                print(f"   ℹ️ Inga nya unika nyheter sparades för {ticker} i denna körning.")

        except Exception as e:
            print(f"❌ Fel vid bearbetning av {ticker}: {e}")

    print("\n--- Synkronisering klar! ---")
run_sync()