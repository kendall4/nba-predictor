# API Keys Setup

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

## NBA API (Injuries)

- Already configured (public API, no key needed)
- Injury status shown automatically in Player Explorer

## Notes

- Free tier: 500 requests/month (enough for ~16 days of checking odds once/day)
- Paid tiers available if you need more requests
- Line shopping requires API key - app will show warning if not set

