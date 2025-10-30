# NBA Prediction ML Models

## Overview
This folder contains the machine learning pipeline for predicting player performance (points, rebounds, assists).

**Before ML:** We used simple heuristics (season avg × pace × defense)  
**With ML:** Models learn complex patterns from historical game data

## How It Works

### Step 1: Build Training Data
```bash
python src/models/build_training_data.py
```

This script:
- Loads historical games (2024-25, 2025-26)
- For each game, matches player features with ACTUAL outcomes
- Features: season averages, opponent defense, pace, etc.
- Targets: what player ACTUALLY scored (PTS/REB/AST)

Output: `data/processed/training_data_2025-26.csv`

### Step 2: Train Models
```bash
python src/models/train_models.py
```

This script:
- Loads training data
- Trains 3 separate models (one per stat: PTS, REB, AST)
- Compares XGBoost, RandomForest, GradientBoosting
- Picks best model for each stat
- Saves to `src/models/saved/*.pkl`

Output: `src/models/saved/PTS_predictor.pkl`, `REB_predictor.pkl`, `AST_predictor.pkl`

### Step 3: Use in Predictions
The `MatchupFeatureBuilder` automatically:
- Loads trained models if they exist
- Uses ML predictions if models are found
- Falls back to heuristics if models aren't trained yet

## Model Architecture

**Features (11 inputs):**
1. season_ppg - Player's season average points
2. season_rpg - Player's season average rebounds
3. season_apg - Player's season average assists
4. season_fg_pct - Player's field goal percentage
5. games_played - Total games played
6. minutes - Average minutes per game
7. expected_pace - Game pace (both teams average)
8. opponent_def_rating - Opponent's defensive rating
9. opponent_off_rating - Opponent's offensive rating
10. pace_factor - Pace adjustment (pace/100)
11. def_factor - Defense adjustment (opp_def/112)

**Targets (3 outputs):**
- actual_PTS - What player actually scored
- actual_REB - What player actually rebounded
- actual_AST - What player actually assisted

## Model Quality

Models are evaluated with:
- **R² Score**: How well model explains variance (1.0 = perfect, 0.0 = no better than guessing average)
- **MAE (Mean Absolute Error)**: Average prediction error in stat units

Typical performance:
- **Points**: R² ~0.6-0.7 (good - points vary a lot)
- **Rebounds**: R² ~0.5-0.6 (decent - rebounds more consistent)
- **Assists**: R² ~0.5-0.6 (decent - assists depend on teammates)

## Why Separate Models?

Points, rebounds, and assists have different patterns:
- Points: More dependent on usage/minutes
- Rebounds: More dependent on position/matchup
- Assists: More dependent on team style/teammates

Training separate models allows each to specialize.

## Retraining

Models should be retrained:
- When new season data is available
- Monthly during season (to capture trends)
- When prediction quality drops

Just run Step 1 and Step 2 again - it will overwrite old models.

