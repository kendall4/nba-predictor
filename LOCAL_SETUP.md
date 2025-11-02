# Running Locally with Streamlit

Streamlit provides an excellent, user-friendly interface for running this app locally! It's much easier than setting up a custom web framework.

## Quick Start

1. **Activate your virtual environment:**
   ```bash
   source venv/bin/activate  # On Mac/Linux
   # or
   venv\Scripts\activate  # On Windows
   ```

2. **Install dependencies (if not already done):**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the Streamlit app:**
   ```bash
   streamlit run app.py
   ```

4. **Open in your browser:**
   - Streamlit will automatically open your browser to `http://localhost:8501`
   - If it doesn't, navigate there manually

## Why Streamlit is Great for Local Use

✅ **Beautiful UI out of the box** - Dark theme, modern design, responsive layouts  
✅ **Interactive widgets** - Sliders, dropdowns, checkboxes, buttons  
✅ **Real-time updates** - Changes reflect immediately  
✅ **No frontend code needed** - Pure Python  
✅ **Built-in caching** - Fast tab switching with `@st.cache_data` and `@st.cache_resource`  
✅ **Mobile-friendly** - Works on tablets/phones too  

## Local Development Tips

### Hot Reload
- Streamlit automatically reloads when you save changes to Python files
- No need to restart the server!

### Viewing Logs
- Check the terminal where you ran `streamlit run app.py` for logs
- Errors will appear both in terminal and in the browser

### Custom Port
```bash
streamlit run app.py --server.port 8502
```

### Custom Theme
Edit `.streamlit/config.toml`:
```toml
[theme]
primaryColor = "#00e5b0"
backgroundColor = "#000000"
secondaryBackgroundColor = "#0a0f0e"
textColor = "#E6F6F3"
```

## Performance

The app is optimized for local use:
- **Preloaded data** - MatchupFeatureBuilder and injury data load once at startup
- **Session state caching** - Predictions cached in memory
- **Fast tab switching** - All data preloaded, no reloading needed

## Troubleshooting

### Port Already in Use
```bash
streamlit run app.py --server.port 8503
```

### Module Not Found
- Make sure you're in the project root directory
- Activate your virtual environment
- Run `pip install -r requirements.txt`

### API Keys
Create a `.env` file in the project root:
```
ODDS_API_KEY=your_key_here
ROTOWIRE_API_KEY=your_key_here  # Optional
```

Or use Streamlit secrets: `.streamlit/secrets.toml`

## Alternatives (if you want something different)

If you want a different UI framework:
- **Flask + Bootstrap** - More control, but requires HTML/CSS/JS
- **FastAPI + React** - More complex, but very powerful
- **Gradio** - Similar to Streamlit, but less mature

**But honestly, Streamlit is perfect for this use case!** It gives you:
- Professional UI with zero frontend code
- All the interactivity you need
- Great performance with caching
- Easy deployment when ready

