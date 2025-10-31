# API Keys Setup

## ✅ NO API KEYS REQUIRED! 

The app works completely **FREE** using ESPN's public injury reports. API keys are **OPTIONAL** for enhanced features.

---

## Rotowire API (Injuries & Lineups) - OPTIONAL

**Note:** Rotowire requires a **paid subscription** and contacting them directly. You don't need this - ESPN provides free injury data!

1. **Get API Key (if desired):**
   - Contact Rotowire directly for API access (requires paid subscription)
   - Visit: https://www.rotowire.com/ (look for API/Developer access)
   - API provides real-time injury reports and expected lineups

2. **Set Environment Variable (optional):**
   
   **Local (`.env` file):**
   ```bash
   ROTOWIRE_API_KEY=your_api_key_here
   ```
   
   **Streamlit Cloud:**
   - Go to your app → Settings → Secrets
   - Add:
     ```
     ROTOWIRE_API_KEY=your_api_key_here
     ```

3. **Usage:**
   - Injury status automatically used when filtering predictions
   - Lineups shown in "🗓️ Games" tab
   - **Without Rotowire:** Falls back to FREE ESPN injury data (works great!)

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

