"""
Model Validation Utility
========================
Compare ML predictions vs actual outcomes to track model performance.
Run this periodically to see if models are accurate or need retraining.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from src.features.matchup_features import MatchupFeatureBuilder

def validate_predictions(date_range=None, min_games=10):
    """
    Compare predictions vs actuals for recent games
    
    Args:
        date_range: Tuple (start_date, end_date) or None for all cached games
        min_games: Minimum games needed to report stats
    
    Returns:
        DataFrame with prediction accuracy metrics
    """
    print("=" * 70)
    print("🔍 MODEL VALIDATION")
    print("=" * 70)
    
    # Load training data (has actual outcomes)
    training_path = 'data/processed/training_data_2025-26.csv'
    if not Path(training_path).exists():
        print("❌ Training data not found. Run build_training_data.py first.")
        return None
    
    df = pd.read_csv(training_path)
    
    if date_range:
        # Filter by date if provided
        df['GAME_DATE'] = pd.to_datetime(df.get('GAME_DATE', pd.NaT), errors='coerce')
        df = df[(df['GAME_DATE'] >= date_range[0]) & (df['GAME_DATE'] <= date_range[1])]
    
    if len(df) < min_games:
        print(f"❌ Not enough games ({len(df)} < {min_games})")
        return None
    
    # Re-run predictions using current models
    builder = MatchupFeatureBuilder(blend_mode="latest")
    
    print(f"\n📊 Validating {len(df)} games...")
    print("   (This may take a few minutes - rerunning predictions)")
    
    results = []
    for idx, row in df.iterrows():
        try:
            # Get prediction for this matchup
            features = builder.get_player_features(
                player_name=row['player_name'],
                opponent_team=row['opponent']
            )
            
            if features:
                results.append({
                    'player': row['player_name'],
                    'opponent': row['opponent'],
                    'actual_PTS': row['actual_PTS'],
                    'actual_REB': row['actual_REB'],
                    'actual_AST': row['actual_AST'],
                    'pred_PTS': features['predicted_points'],
                    'pred_REB': features['predicted_rebounds'],
                    'pred_AST': features['predicted_assists'],
                })
        except Exception as e:
            continue
        
        if (idx + 1) % 50 == 0:
            print(f"   Processed {idx + 1}/{len(df)}...")
    
    results_df = pd.DataFrame(results)
    
    if len(results_df) == 0:
        print("❌ No valid predictions generated")
        return None
    
    # Calculate metrics
    metrics = []
    for stat in ['PTS', 'REB', 'AST']:
        actual_col = f'actual_{stat}'
        pred_col = f'pred_{stat}'
        
        mae = np.abs(results_df[pred_col] - results_df[actual_col]).mean()
        rmse = np.sqrt(((results_df[pred_col] - results_df[actual_col]) ** 2).mean())
        mean_actual = results_df[actual_col].mean()
        mean_pred = results_df[pred_col].mean()
        
        # Accuracy: within 2 of actual
        within_2 = (np.abs(results_df[pred_col] - results_df[actual_col]) <= 2).mean()
        
        metrics.append({
            'stat': stat,
            'mae': mae,
            'rmse': rmse,
            'mean_actual': mean_actual,
            'mean_pred': mean_pred,
            'bias': mean_pred - mean_actual,  # Positive = overpredicting
            'within_2_pct': within_2 * 100
        })
    
    metrics_df = pd.DataFrame(metrics)
    
    print("\n" + "=" * 70)
    print("📊 VALIDATION RESULTS")
    print("=" * 70)
    print("\n" + metrics_df.to_string(index=False))
    
    print("\n💡 Metrics:")
    print("   MAE: Mean Absolute Error (lower is better)")
    print("   RMSE: Root Mean Squared Error (lower is better)")
    print("   Bias: Prediction avg - Actual avg (0 = perfect, + = overpredicting)")
    print("   Within 2%: % of predictions within 2 units of actual")
    
    return metrics_df

if __name__ == "__main__":
    validate_predictions()

