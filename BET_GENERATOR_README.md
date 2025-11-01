# Bet Generator - Mainline & Longshot Model

A betting recommendation system that outputs both **mainline** (conservative) and **longshot** (high-odds) options with Expected Value (EV), Fair Value (FV), and unit sizing.

## Features

- 📊 **Mainline Options**: Conservative bets (odds ≤ +200)
- 🚀 **Longshot Options**: High-odds bets (odds ≥ +500)
- 💰 **EV Calculation**: Expected Value for each bet
- 🎯 **Fair Value**: Calculated true odds vs. sportsbook odds
- 📏 **Unit Sizing**: Kelly Criterion (fractional, 25% of full Kelly)
- 📈 **Sorted by EV**: Best value bets first

## Output Format

The generator outputs bets in multiple formats:

### Detailed Format (Default)
```
Austin Reaves Over 24.5 Points +1140 (0.23u - FV: +757) @ CZR
Walker Kessler Over 16.5 Rebounds +1280 (0.52u - FV: +567) @ DK
Trae Young Over 8.5 Assists -130 (0.85u - FV: -177) @ FD
```

### EV Format
```
Trae Young Over 8.5 Assists (-130 - FV -177): EV=0.13
Day'Ron Sharpe Over 4.5 Points (-215 - FV -319): EV=0.12
Harrison Barnes Over 0.5 Threes (-456 - FV -842): EV=0.09
```

## Usage

### Command Line

```bash
# Generate points bets with minimum EV of 0.0
python generate_bets.py points 0.0

# Generate rebounds bets with minimum EV of 0.05
python generate_bets.py rebounds 0.05

# Generate assists bets (include slightly negative EV)
python generate_bets.py assists -0.02
```

### Python API

```python
from src.analysis.bet_generator import BetGenerator
import pandas as pd

# Load your predictions
predictions = pd.read_csv('predictions_today.csv')

# Initialize generator
generator = BetGenerator(odds_api_key=os.getenv('ODDS_API_KEY'))

# Generate bets
bets_df = generator.generate_all_bets(
    predictions,
    stat_type='points',
    min_ev=0.0,
    include_negative_ev=False
)

# Display results
generator.print_bets(
    bets_df,
    separate_mainline_longshot=True,
    min_ev=0.0,
    max_display=100
)
```

## Requirements

1. **ODDS_API_KEY**: Set your The Odds API key
   ```bash
   export ODDS_API_KEY=your_key_here
   ```

2. **Predictions**: You need player predictions (from `predictions_today.csv` or generate them)

## Understanding the Output

### Mainline Options (Odds ≤ +200)
- **Conservative bets** with higher probability
- Lower risk, lower reward
- Example: `Over 24.5 Points -110 (0.96u - FV: -177)`

### Longshot Options (Odds ≥ +500)
- **High-odds bets** with lower probability but higher payout
- Higher risk, higher reward
- Example: `Over 39.5 Points +3200 (0.15u - FV: +1761)`

### Key Metrics

- **EV (Expected Value)**: Average profit per $1 bet. Positive EV = profitable long-term
- **FV (Fair Value)**: True odds based on your model's probability
- **Units**: Recommended bet size using Kelly Criterion (0.25 fractional = safer)
  - Example: `0.5u` = bet 0.5% of bankroll
  - Example: `1.2u` = bet 1.2% of bankroll

### Reading the Output

```
Austin Reaves Over 24.5 Points +1140 (0.23u - FV: +757) @ CZR
```

- **Austin Reaves**: Player name
- **Over 24.5 Points**: Bet on scoring more than 24.5 points
- **+1140**: Sportsbook odds (bet $100 to win $1140)
- **0.23u**: Recommended bet size (0.23 units = 0.23% of bankroll)
- **FV: +757**: Your model's fair value odds (sportsbook is offering better odds than fair value = value bet)
- **@ CZR**: Caesars sportsbook

## Customization

### Adjust Thresholds

```python
generator = BetGenerator(odds_api_key=api_key)
generator.mainline_threshold = +150  # Lower threshold = stricter mainline
generator.longshot_threshold = +1000    # Higher threshold = only extreme longshots
```

### Change Unit Sizing

Modify the `kelly_criterion_unit` method or change `bankroll_fraction`:

```python
# Safer: 0.1 = 10% of full Kelly (very conservative)
# Default: 0.25 = 25% of full Kelly
# Aggressive: 0.5 = 50% of full Kelly
units = generator.kelly_criterion_unit(prob, odds, bankroll_fraction=0.1)
```

### Custom Output Format

```python
# Simple format
print(generator.format_bet_line(bet, format_style='simple'))

# EV format
print(generator.format_bet_line(bet, format_style='ev'))
```

## How It Works

1. **Fetch Odds**: Gets all available player props from multiple sportsbooks
2. **Match Players**: Matches your predictions with available odds
3. **Calculate Probability**: Uses normal distribution to estimate probability of hitting the line
4. **Calculate EV**: `EV = (Probability × Payout) - (1 - Probability) × Stake`
5. **Calculate Fair Value**: Converts probability back to odds
6. **Calculate Units**: Uses Kelly Criterion (fractional) for bet sizing
7. **Categorize**: Separates mainline vs longshot
8. **Sort & Display**: Shows best value bets first

## Tips

- **Higher EV = Better Value**: Focus on bets with EV > 0.05 (5%+ edge)
- **Compare FV to Odds**: If odds are better than FV, that's a value bet
- **Unit Sizing**: Never bet more than recommended units (Kelly is already aggressive)
- **Diversify**: Don't put all units on one bet
- **Bankroll Management**: If using units, make sure 1 unit = 1% of your bankroll

## Output Files

The script saves all bets to CSV:
```
bets_points_20250115.csv
bets_rebounds_20250115.csv
```

Columns: `player`, `stat`, `direction`, `line`, `odds`, `probability`, `ev`, `fv_odds`, `units`, `book`, `is_mainline`, `is_longshot`

