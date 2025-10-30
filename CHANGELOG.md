# Changelog

## Recent Updates

### ML/AI Integration
- ✅ Added ML model training pipeline (`src/models/`)
  - Training data builder: Creates dataset from historical games
  - Model trainer: Trains XGBoost/RandomForest models for PTS/REB/AST
  - Automatic fallback to heuristics if models not trained
- ✅ Enhanced predictions with ML models when available
- ✅ Model validation utility to track prediction accuracy

### H2H (Head-to-Head) Improvements
- ✅ H2H consistency now includes previous season if current season has < 5 games
- ✅ Returns last 5 H2H games total (prioritizing current season)
- ✅ Added H2H summary utility (`src/utils/h2h_stats.py`)
- ✅ Player Explorer now shows H2H stats vs today's opponent

### UI/UX Improvements
- ✅ Split NBA UI into modular sub-tabs (Leaderboard, Predictions, Hot Hand, Live SGP, Lines Explorer, Player Explorer, Games)
- ✅ Dark theme with teal accents
- ✅ Cached predictions in session state for faster navigation
- ✅ Fixed timeout errors with better error handling

### Utilities Added
- ✅ Model validator: Compare predictions vs actuals
- ✅ H2H stats: Detailed head-to-head summaries
- ✅ Better error handling for NBA API timeouts

### Bug Fixes
- ✅ Fixed duplicate players in predictions
- ✅ Fixed Streamlit experimental_data_editor deprecation
- ✅ Improved NBA API timeout handling

## Usage

### Training ML Models
```bash
# Step 1: Build training data
python src/models/build_training_data.py

# Step 2: Train models
python src/models/train_models.py

# Models automatically used in predictions after training
```

### Model Validation
```bash
python src/utils/model_validator.py
```

### H2H Stats
```python
from src.utils.h2h_stats import get_h2h_summary, display_h2h_summary
summary = get_h2h_summary('Luka Dončić', 'BOS')
display_h2h_summary(summary)
```

