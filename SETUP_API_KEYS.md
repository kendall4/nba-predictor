# API Keys Setup

## Rotowire API (Injuries & Lineups) - RECOMMENDED

1. **Get API Key:**
   - Contact Rotowire directly for API access
   - Visit: https://www.rotowire.com/ (look for API/Developer access)
   - API provides real-time injury reports and expected lineups

2. **Set Environment Variable:**
   
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
   - Falls back to NBA API if Rotowire unavailable

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

## NBA API (Fallback)

- Already configured (public API, no key needed)
- Used as fallback if Rotowire unavailable
- Injury status shown automatically in Player Explorer

## Notes

- **Rotowire**: Best source for injuries/lineups, requires contact for API access
- **The Odds API**: Free tier: 500 requests/month
- Both APIs are optional - app works without them (with reduced features)

