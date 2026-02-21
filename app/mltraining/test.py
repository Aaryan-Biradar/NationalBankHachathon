import pandas as pd
import numpy as np
import xgboost as xgb
import sys

# Trader type mapping
TRADER_TYPES = {
    0: 'calm_trader',
    1: 'loss_averse_trader',
    2: 'overtrader',
    3: 'revenge_trader'
}

def predict_trader_type(csv_file):
    """
    Load CSV file and predict trader type using the trained XGBoost model.
    Uses the improved v2 feature set (97.62% accuracy model).
    
    Args:
        csv_file: Path to the CSV file to predict
    """
    # Load the trained model
    model = xgb.XGBClassifier()
    model.load_model('trader_classifier.json')
    
    # Load the CSV file
    df = pd.read_csv(csv_file)
    
    # Data cleaning
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    
    # Handle missing profit_loss
    if df['profit_loss'].isna().any():
        df.loc[df['profit_loss'].isna(), 'profit_loss'] = (
            df.loc[df['profit_loss'].isna(), 'exit_price'] - 
            df.loc[df['profit_loss'].isna(), 'entry_price']
        )
    
    # Drop rows with missing critical columns
    df = df.dropna(subset=['quantity', 'side', 'timestamp', 'entry_price', 'exit_price'])
    
    # Remove balance column if it exists
    if 'balance' in df.columns:
        df = df.drop('balance', axis=1)
    
    # Sort by timestamp for sequential features
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    # === BASIC FEATURES ===
    df['side_encoded'] = (df['side'] == 'BUY').astype(int)
    df['profit_loss_actual'] = df['profit_loss']
    df['is_profit'] = (df['profit_loss'] > 0).astype(int)
    df['loss_amount'] = df['profit_loss'].apply(lambda x: abs(x) if x < 0 else 0)
    
    df['price_range'] = df['exit_price'] - df['entry_price']
    df['price_range_pct'] = (df['price_range'] / (df['entry_price'].abs() + 1e-6)) * 100
    df['trade_value'] = df['quantity'] * df['entry_price']
    
    # === WINDOWED BEHAVIORAL PATTERNS ===
    window_sizes = [20, 50]
    
    for window in window_sizes:
        df[f'win_rate_{window}'] = df['is_profit'].rolling(window, min_periods=1).mean().fillna(0.5)
        df[f'avg_qty_{window}'] = df['quantity'].rolling(window, min_periods=1).mean().fillna(df['quantity'].mean())
        df[f'qty_volatility_{window}'] = df['quantity'].rolling(window, min_periods=1).std().fillna(0)
        df[f'qty_max_{window}'] = df['quantity'].rolling(window, min_periods=1).max().fillna(0)
        
        df[f'avg_profit_{window}'] = df['profit_loss'].rolling(window, min_periods=1).mean().fillna(0)
        df[f'profit_std_{window}'] = df['profit_loss'].rolling(window, min_periods=1).std().fillna(0)
        df[f'max_drawdown_{window}'] = df['profit_loss'].rolling(window, min_periods=1).min().fillna(0)
        
        df[f'buy_ratio_{window}'] = df['side_encoded'].rolling(window, min_periods=1).mean().fillna(0.5)
    
    # === LOSS AVERSION INDICATORS ===
    early_close = []
    for idx in range(len(df)):
        if idx > 0:
            prev_profit = df.loc[idx-1, 'profit_loss']
            curr_profit = df.loc[idx, 'profit_loss']
            if prev_profit > 0 and curr_profit > prev_profit:
                early_close.append(1)
            else:
                early_close.append(0)
        else:
            early_close.append(0)
    df['early_close_indicator'] = early_close
    
    # === REVENGE TRADING INDICATORS ===
    qty_after_loss = []
    for idx in range(len(df)):
        if idx > 0 and df.loc[idx-1, 'profit_loss'] < 0:
            qty_ratio = df.loc[idx, 'quantity'] / (df.loc[idx-1, 'quantity'] + 1e-6)
            qty_after_loss.append(qty_ratio)
        else:
            qty_after_loss.append(0.0)
    df['qty_after_loss'] = qty_after_loss
    
    
    # Select features (must match training features)
    features = [col for col in df.columns if col not in 
                ['timestamp', 'asset', 'side', 'profit_loss', 'exit_price', 'entry_price']]
    
    X = df[features].fillna(0).replace([np.inf, -np.inf], 0)
    
    # Make predictions
    predictions = model.predict(X)
    probabilities = model.predict_proba(X)
    
    # Get most common trader type
    unique, counts = np.unique(predictions, return_counts=True)
    most_common_idx = unique[np.argmax(counts)]
    most_common_type = TRADER_TYPES[most_common_idx]
    confidence = np.max(probabilities, axis=1).mean()
    
    # Display results
    print(f"\n{'='*70}")
    print(f"📊 TRADER TYPE PREDICTION RESULTS")
    print(f"{'='*70}")
    print(f"File: {csv_file}")
    print(f"Total samples analyzed: {len(df)}")
    print(f"\n🎯 PRIMARY TRADER TYPE: {most_common_type.replace('_', ' ').upper()}")
    print(f"Confidence: {confidence*100:.2f}%")
    
    print(f"\n📈 Prediction Distribution:")
    print(f"{'='*70}")
    for idx, count in zip(unique, counts):
        pct = count / len(predictions) * 100
        trader_label = TRADER_TYPES[idx].replace('_', ' ').title()
        bar = '█' * int(pct / 5)
        print(f"  {trader_label:<25} {count:>5} samples ({pct:>5.1f}%) {bar}")
    
    print(f"\nAverage prediction confidence: {confidence*100:.2f}%")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_v2.py <csv_file>")
        print("Example: python test_v2.py ../../datasets/calm_trader.csv")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    predict_trader_type(csv_file)
