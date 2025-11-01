"""
Odds Utility Functions
======================
Helper functions for odds calculations including implied probability
"""

def american_to_implied_prob(american_odds: int) -> float:
    """
    Convert American odds to implied probability (0-1)
    
    Args:
        american_odds: American odds format (e.g., -110, +150, +500)
    
    Returns:
        Implied probability as decimal (0.0 to 1.0)
    """
    if american_odds > 0:
        # Positive odds: probability = 100 / (odds + 100)
        return 100 / (american_odds + 100)
    else:
        # Negative odds: probability = abs(odds) / (abs(odds) + 100)
        return abs(american_odds) / (abs(american_odds) + 100)

def implied_prob_to_percent(american_odds: int) -> str:
    """
    Convert American odds to implied probability percentage string
    
    Args:
        american_odds: American odds format
    
    Returns:
        Formatted percentage string (e.g., "52.4%", "48.3%")
    """
    prob = american_to_implied_prob(american_odds)
    return f"{prob * 100:.1f}%"

def calculate_implied_prob_from_line(line: float, prediction: float, std_dev: float = None) -> float:
    """
    Calculate implied probability from a line and prediction
    
    This is the model's true probability, not the sportsbook's implied prob
    
    Args:
        line: The betting line (e.g., 24.5 points)
        prediction: Model's prediction (e.g., 26.2 points)
        std_dev: Standard deviation (defaults to 20% of prediction)
    
    Returns:
        Probability (0-1) that prediction exceeds line
    """
    from scipy.stats import norm
    
    if std_dev is None:
        std_dev = prediction * 0.20  # 20% variance assumption
    
    # Prevent division by zero - ensure std_dev is at least 0.5
    if std_dev < 0.5:
        std_dev = max(0.5, abs(prediction) * 0.1)  # Use 10% of prediction or 0.5, whichever is larger
    
    # If prediction is zero or very small, return neutral probability
    if abs(prediction) < 0.1:
        return 0.5
    
    # Z-score
    z = (line - prediction) / std_dev
    
    # Probability of being over the line
    prob_over = 1 - norm.cdf(z)
    
    # Clamp to valid range [0, 1]
    return max(0.0, min(1.0, prob_over))

