# Quick Setup: Rotowire API Key

## Why You Need It

The app now **requires** confirmed lineups (no more estimated/minutes-based). Rotowire API provides confirmed starting lineups which are critical for accurate top plays analysis.

## Step-by-Step Setup

### 1. Get Your Rotowire API Key

- Visit https://www.rotowire.com/
- Contact them for API access (paid subscription required)
- They'll provide you with an API key

### 2. Set the API Key (Choose One Method)

#### Method 1: `.env` File (Easiest for Local Development) ✅

1. Create a file named `.env` in the project root:
   ```bash
   cd /Users/kendall/Documents/projects/nba-predictor
   touch .env
   ```

2. Open `.env` in a text editor and add:
   ```
   ROTOWIRE_API_KEY=your_actual_api_key_here
   ```

3. Replace `your_actual_api_key_here` with your real API key (no quotes needed)

4. Save the file

5. **Important:** Make sure `.env` is in `.gitignore` so you don't accidentally commit your API key!

#### Method 2: Streamlit Secrets (For Streamlit Cloud)

1. Go to https://share.streamlit.io/
2. Select your app
3. Click "Settings" (⚙️ icon)
4. Click "Secrets"
5. Add:
   ```
   ROTOWIRE_API_KEY = "your_actual_api_key_here"
   ```
6. Click "Save"
7. Your app will automatically redeploy

### 3. Verify It Works

1. Run the app: `streamlit run app.py`
2. Navigate to "🗓️ Games" tab
3. Select any game
4. You should see: **"✅ Confirmed lineup available"** instead of error messages

### 4. Troubleshooting

**Still seeing "No confirmed lineup available"?**

- Check that your `.env` file is in the project root (same folder as `app.py`)
- Make sure there are no spaces around the `=` sign: `ROTOWIRE_API_KEY=key` (not `ROTOWIRE_API_KEY = key`)
- Restart the Streamlit app after creating/modifying `.env`
- Check the terminal for any error messages
- Verify your API key is correct (no typos)

**For Streamlit Cloud:**
- Make sure you saved the secrets
- Wait for the app to redeploy
- Check the "Manage app" logs for any errors

### Example `.env` File

```bash
# API Keys for NBA Predictor
ROTOWIRE_API_KEY=rw_abc123xyz789yourkeyhere
ODDS_API_KEY=odds_api_key_here  # Optional but recommended
```

**Remember:**
- Don't share your `.env` file
- Don't commit it to git
- It's already in `.gitignore` by default

