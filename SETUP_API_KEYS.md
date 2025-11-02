# API Keys Setup

## ✅ NO API KEYS REQUIRED! 

The app works completely **FREE** using ESPN's public injury reports. API keys are **OPTIONAL** for enhanced features.

---

## Rotowire API (Injuries & Lineups) - REQUIRED FOR CONFIRMED LINEUPS

**⚠️ IMPORTANT:** Confirmed lineups require Rotowire API key. Without it, the Games tab will show "No confirmed lineup available" errors.

**Note:** Rotowire requires a **paid subscription** and contacting them directly.

1. **Get API Key:**
   - Contact Rotowire directly for API access (requires paid subscription)
   - Visit: https://www.rotowire.com/ (look for API/Developer access)
   - Email them or check their website for API access
   - API provides real-time injury reports and **confirmed starting lineups**

2. **Set Environment Variable:**
   
   **Option A: Local (`.env` file) - RECOMMENDED for local development:**
   
   Create a `.env` file in the project root directory:
   ```bash
   # In the project root: /Users/kendall/Documents/projects/nba-predictor/.env
   ROTOWIRE_API_KEY=your_api_key_here
   ODDS_API_KEY=your_odds_api_key_here  # Optional but recommended
   ```
   
   The app will automatically load this file (python-dotenv is installed).
   
   **Option B: Streamlit Secrets (for Streamlit Cloud):**
   - Go to your Streamlit Cloud app → Settings → Secrets
   - Click "Edit secrets"
   - Add:
     ```
     ROTOWIRE_API_KEY = "your_api_key_here"
     ODDS_API_KEY = "your_odds_api_key_here"
     ```
   - Save and redeploy
   
   **Option C: System Environment Variable:**
   ```bash
   # Mac/Linux
   export ROTOWIRE_API_KEY=your_api_key_here
   
   # Windows (PowerShell)
   $env:ROTOWIRE_API_KEY="your_api_key_here"
   ```

3. **Verify it's working:**
   - Run the app: `streamlit run app.py`
   - Go to "🗓️ Games" tab
   - Select a game - you should see "✅ Confirmed lineup available" instead of error messages
   - Without Rotowire: Will show error "❌ No confirmed lineup available"

4. **Usage:**
   - **Confirmed lineups** shown in "🗓️ Games" tab (REQUIRED for accurate top plays)
   - Injury status automatically used when filtering predictions
   - **Without Rotowire:** Cannot show confirmed lineups (accuracy critical for top plays)

## The Odds API (Line Shopping)

1. **Get Free API Key:**
   - Visit: https://the-odds-api.com/
   - Sign up for free account (500 requests/month)
   - Copy your API key

2. **Set Environment Variable:**
   
   **Local (`.env` file):**
   ```bash
   ODDS_API_KEY=your_api_key_here
   ```
   
   **Streamlit Cloud:**
   - Go to your app → Settings → Secrets
   - Add:
     ```
     ODDS_API_KEY=your_api_key_here
     ```

3. **Usage:**
   - Navigate to "💰 Line Shopping" tab in NBA section
   - Select player and stat
   - Click "Fetch Live Odds" to compare across books

## ESPN Injury Reports (FREE - DEFAULT)

- **No API key needed!** Works automatically
- Scrapes public ESPN NBA injury reports
- Used automatically if Rotowire API key not provided
- Updates daily with current injury status

## NBA API (Fallback)

- Already configured (public API, no key needed)
- Used as final fallback if ESPN unavailable
- Injury status shown automatically in Player Explorer

## Notes

- **🎉 FREE TO USE:** ESPN injury data works without any API keys!
- **Rotowire**: Premium option (paid subscription) - only needed if you want their specific data format
- **The Odds API**: Free tier: 500 requests/month
- **All APIs are optional** - app works great with just ESPN (free)!

