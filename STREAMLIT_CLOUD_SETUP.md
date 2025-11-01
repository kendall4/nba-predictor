# Streamlit Cloud Setup Guide

This guide helps you deploy the NBA Predictor app to Streamlit Cloud.

## Prerequisites

1. **GitHub Repository**: Your code should be in a GitHub repo
2. **Streamlit Cloud Account**: Sign up at https://streamlit.io/cloud

## Deployment Steps

### 1. Connect Repository

1. Go to https://share.streamlit.io/
2. Click "New app"
3. Select your GitHub repository
4. Set:
   - **Branch**: `main`
   - **Main file path**: `app.py`

### 2. Configure Secrets

Click "Advanced settings" → "Secrets" and add:

```toml
ODDS_API_KEY = "your_odds_api_key_here"
ROTOWIRE_API_KEY = "your_rotowire_api_key_here"  # Optional
```

### 3. Deploy

Click "Deploy" and wait for the build to complete.

## What's Configured

✅ **Timeout handling**: All API calls have retry logic (1-2 retries, fast failures)
✅ **Error suppression**: Verbose timeout errors are suppressed in logs
✅ **Caching**: Game data cached for 5 minutes
✅ **Fallback handling**: Graceful fallbacks when APIs fail
✅ **Streamlit config**: Theme and settings configured

## Performance Optimizations

- **Fast retries**: Only 1 retry with 0.5s delay (no long waits)
- **Smart caching**: Game logs cached after first fetch
- **Background processing**: Heavy operations don't block UI

## Troubleshooting

### App is slow
- First load may be slow (fetching data)
- Subsequent loads use cache (fast)
- Check if API keys are set (fallbacks slow things down)

### Timeout errors
- Normal - API may be slow
- App will retry once and fallback gracefully
- Errors are suppressed to reduce log spam

### No data showing
- Check API keys in Secrets
- Verify branch is `main` and main file is `app.py`
- Check logs in Streamlit Cloud dashboard

## Files Included

- `.streamlit/config.toml` - Streamlit configuration
- `.streamlit/secrets.toml.example` - Secrets template
- `requirements.txt` - All dependencies

## Notes

- Data cache files (`data/cache/`) are gitignored and won't persist
- First-time game log fetches will be slower (no cache)
- Subsequent visits will be faster (data cached)

