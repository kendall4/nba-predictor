"""
Step 2: Train ML Models
======================
This script:
1. Loads the training data (features + actual outcomes)
2. Trains separate models for PTS, REB, AST
3. Compares XGBoost vs RandomForest vs GradientBoosting
4. Saves the best model for each stat

Why separate models? Points, rebounds, assists have different patterns!
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from xgboost import XGBRegressor
import joblib
import os

def load_training_data(path='data/processed/training_data_2025-26.csv'):
    """Load the training dataset we built"""
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Training data not found: {path}\n"
            "Run: python src/models/build_training_data.py first"
        )
    return pd.read_csv(path)

def prepare_features(df):
    """
    Prepare feature matrix X and target vectors y
    
    Features (what we know BEFORE the game):
    - Player's season averages
    - Opponent's defense
    - Game pace
    - etc.
    
    Targets (what we want to PREDICT):
    - actual_PTS, actual_REB, actual_AST
    """
    # Feature columns (inputs)
    feature_cols = [
        'season_ppg', 'season_rpg', 'season_apg',
        'season_fg_pct', 'games_played', 'minutes',
        'expected_pace', 'opponent_def_rating', 'opponent_off_rating',
        'pace_factor', 'def_factor'
    ]
    
    # Remove rows with missing features
    df_clean = df.dropna(subset=feature_cols)
    
    X = df_clean[feature_cols].values
    y_pts = df_clean['actual_PTS'].values
    y_reb = df_clean['actual_REB'].values
    y_ast = df_clean['actual_AST'].values
    
    return X, y_pts, y_reb, y_ast, feature_cols

def train_model_for_stat(X_train, y_train, X_test, y_test, stat_name, feature_names):
    """
    Train multiple models and pick the best one
    
    Returns: (best_model, best_score, model_name)
    """
    models_to_try = {
        'xgboost': XGBRegressor(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42
        ),
        'gradient_boosting': GradientBoostingRegressor(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42
        ),
        'random_forest': RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=-1
        )
    }
    
    best_score = -np.inf
    best_model = None
    best_name = None
    results = {}
    
    print(f"\n🧪 Training models for {stat_name}...")
    
    for name, model in models_to_try.items():
        # Train
        model.fit(X_train, y_train)
        
        # Evaluate
        y_pred = model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        
        results[name] = {
            'mae': mae,
            'r2': r2,
            'model': model
        }
        
        print(f"  {name:20s} MAE: {mae:.2f}, R²: {r2:.3f}")
        
        # R² measures how well model explains variance (higher = better)
        if r2 > best_score:
            best_score = r2
            best_model = model
            best_name = name
    
    print(f"  ✅ Best: {best_name} (R² = {best_score:.3f})")
    
    # Feature importance (which features matter most?)
    if hasattr(best_model, 'feature_importances_'):
        importances = best_model.feature_importances_
        feature_imp = pd.DataFrame({
            'feature': feature_names,
            'importance': importances
        }).sort_values('importance', ascending=False)
        print(f"\n  Top 5 Features:")
        for _, row in feature_imp.head(5).iterrows():
            print(f"    {row['feature']:20s} {row['importance']:.3f}")
    
    return best_model, best_score, best_name

def main():
    print("=" * 70)
    print("🤖 ML MODEL TRAINER")
    print("=" * 70)
    
    # Load training data
    print("\n📂 Loading training data...")
    df = load_training_data()
    print(f"   Loaded {len(df)} examples")
    
    # Prepare features and targets
    X, y_pts, y_reb, y_ast, feature_names = prepare_features(df)
    print(f"   Features: {len(feature_names)} columns")
    print(f"   Examples: {len(X)} rows")
    
    # Split: 80% train, 20% test
    X_train, X_test, y_pts_train, y_pts_test = train_test_split(
        X, y_pts, test_size=0.2, random_state=42
    )
    _, _, y_reb_train, y_reb_test = train_test_split(
        X, y_reb, test_size=0.2, random_state=42
    )
    _, _, y_ast_train, y_ast_test = train_test_split(
        X, y_ast, test_size=0.2, random_state=42
    )
    
    print(f"\n📊 Train/Test Split:")
    print(f"   Train: {len(X_train)} examples")
    print(f"   Test:  {len(X_test)} examples")
    
    # Train models for each stat
    os.makedirs('src/models/saved', exist_ok=True)
    
    stats = [
        ('PTS', y_pts_train, y_pts_test),
        ('REB', y_reb_train, y_reb_test),
        ('AST', y_ast_train, y_ast_test)
    ]
    
    trained_models = {}
    
    for stat_name, y_train, y_test in stats:
        model, score, name = train_model_for_stat(
            X_train, y_train, X_test, y_test, stat_name, feature_names
        )
        
        # Save model
        model_path = f'src/models/saved/{stat_name}_predictor.pkl'
        joblib.dump(model, model_path)
        print(f"  💾 Saved to {model_path}")
        
        trained_models[stat_name] = {
            'model': model,
            'score': score,
            'name': name
        }
    
    print("\n" + "=" * 70)
    print("✅ TRAINING COMPLETE!")
    print("=" * 70)
    print("\n📊 Model Performance Summary:")
    for stat, info in trained_models.items():
        print(f"   {stat:5s} - {info['name']:20s} R² = {info['score']:.3f}")
    print("\n💡 R² (R-squared) measures model quality:")
    print("   - 1.0 = Perfect predictions")
    print("   - 0.8+ = Very good")
    print("   - 0.5+ = Decent")
    print("   - 0.0 = No better than guessing average")
    print("\n🎯 Models saved! Ready to use in predictions.")

if __name__ == "__main__":
    main()

