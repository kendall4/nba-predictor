#!/bin/bash

# Script to help with Streamlit port issues

echo "🔍 Checking Streamlit processes..."
echo ""

# Check what's using port 8501
echo "Processes using port 8501:"
lsof -i :8501 2>/dev/null || echo "   No processes found (or permission denied)"
echo ""

# Option 1: Kill existing Streamlit process
echo "Option 1: Kill existing Streamlit on port 8501"
echo "   Run: lsof -ti :8501 | xargs kill -9"
echo ""

# Option 2: Run on different port
echo "Option 2: Run on different port (8502)"
echo "   Run: streamlit run app.py --server.port 8502"
echo ""

# Option 3: Check if it's already accessible
echo "Option 3: Check if http://localhost:8501 is already working"
echo "   Open: http://localhost:8501 in your browser"
echo ""

echo "💡 Recommendation:"
echo "   1. First, try opening http://localhost:8501 in your browser"
echo "   2. If it works, you're all set!"
echo "   3. If not, kill the process and restart:"
echo "      lsof -ti :8501 | xargs kill -9"
echo "      streamlit run app.py"

