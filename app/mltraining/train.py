import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from sklearn.utils.class_weight import compute_sample_weight

print("=" * 80)
print("TRADER TYPE CLASSIFICATION - IMPROVED V2")
print("=" * 80)

def prepare_features(df: pl.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    work_df = df.with_columns(
        pl.when(pl.col("profit_loss").is_null())
        .then(pl.col("exit_price") - pl.col("entry_price"))
        .otherwise(pl.col("profit_loss"))
        .alias("profit_loss")
    ).drop_nulls(subset=["quantity", "side", "timestamp", "entry_price", "exit_price"])

    if "balance" in work_df.columns:
        work_df = work_df.drop("balance")

    work_df = work_df.with_columns(
        pl.col("timestamp").cast(pl.Utf8).str.strptime(pl.Datetime, strict=False).alias("timestamp")
    ).sort("timestamp")

    work_df = work_df.with_columns(
        [
            (pl.col("side") == "BUY").cast(pl.Int64).alias("side_encoded"),
            pl.col("profit_loss").cast(pl.Float64, strict=False).alias("profit_loss_actual"),
            (pl.col("profit_loss").cast(pl.Float64, strict=False) > 0)
            .cast(pl.Int64)
            .alias("is_profit"),
            pl.when(pl.col("profit_loss").cast(pl.Float64, strict=False) < 0)
            .then(pl.col("profit_loss").cast(pl.Float64, strict=False).abs())
            .otherwise(0.0)
            .alias("loss_amount"),
            (
                pl.col("exit_price").cast(pl.Float64, strict=False)
                - pl.col("entry_price").cast(pl.Float64, strict=False)
            ).alias("price_range"),
            (
                (
                    pl.col("exit_price").cast(pl.Float64, strict=False)
                    - pl.col("entry_price").cast(pl.Float64, strict=False)
                )
                / (pl.col("entry_price").cast(pl.Float64, strict=False).abs() + 1e-6)
                * 100
            ).alias("price_range_pct"),
            (
                pl.col("quantity").cast(pl.Float64, strict=False)
                * pl.col("entry_price").cast(pl.Float64, strict=False)
            ).alias("trade_value"),
        ]
    )

# Drop rows with missing critical columns
critical_cols = ['quantity', 'side', 'timestamp', 'entry_price', 'exit_price']
df = df.dropna(subset=critical_cols)

# Remove balance column
if 'balance' in df.columns:
    df = df.drop('balance', axis=1)

removed_rows = initial_rows - len(df)
print(f"✓ Removed {removed_rows} rows")
print(f"✓ Dataset after cleaning: {len(df)} rows\n")

# Convert timestamp
df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')

# ============================================================================
# FEATURE ENGINEERING - First: Basic Features on All Data
# ============================================================================
print("⚙️  Engineering behavioral features...")

# === BASIC FEATURES (computed once for all) ===
# df['hour'] = df['timestamp'].dt.hour
# df['day'] = df['timestamp'].dt.day
df['side_encoded'] = (df['side'] == 'BUY').astype(int)
df['profit_loss_actual'] = df['profit_loss']
df['is_profit'] = (df['profit_loss'] > 0).astype(int)
df['loss_amount'] = df['profit_loss'].apply(lambda x: abs(x) if x < 0 else 0)

df['price_range'] = df['exit_price'] - df['entry_price']
df['price_range_pct'] = (df['price_range'] / (df['entry_price'].abs() + 1e-6)) * 100
df['trade_value'] = df['quantity'] * df['entry_price']

# ============================================================================
# Per Trader Type: Windowed Behavioral Patterns
# ============================================================================
for trader_type in [0, 1, 2, 3]:
    mask = df['trader_type'] == trader_type
    trader_indices = df[mask].index
    trader_df = df.loc[trader_indices].sort_values('timestamp').reset_index(drop=True)
    
    # === WINDOWED BEHAVIORAL PATTERNS ===
    window_sizes = [20, 50]
    
    for window in window_sizes:
        # Win rate in window
        win_rate = trader_df['is_profit'].rolling(window, min_periods=1).mean().values
        df.loc[trader_indices, f'win_rate_{window}'] = win_rate
        
        # Quantity patterns
        avg_qty = trader_df['quantity'].rolling(window, min_periods=1).mean().values
        df.loc[trader_indices, f'avg_qty_{window}'] = avg_qty
        
        qty_vol = trader_df['quantity'].rolling(window, min_periods=1).std().values
        df.loc[trader_indices, f'qty_volatility_{window}'] = qty_vol
        
        qty_max = trader_df['quantity'].rolling(window, min_periods=1).max().values
        df.loc[trader_indices, f'qty_max_{window}'] = qty_max
        
        # Profit patterns
        avg_profit = trader_df['profit_loss'].rolling(window, min_periods=1).mean().values
        df.loc[trader_indices, f'avg_profit_{window}'] = avg_profit
        
        profit_std = trader_df['profit_loss'].rolling(window, min_periods=1).std().values
        df.loc[trader_indices, f'profit_std_{window}'] = profit_std
        
        max_dd = trader_df['profit_loss'].rolling(window, min_periods=1).min().values
        df.loc[trader_indices, f'max_drawdown_{window}'] = max_dd
        
        # Buy ratio
        buy_ratio = trader_df['side_encoded'].rolling(window, min_periods=1).mean().values
        df.loc[trader_indices, f'buy_ratio_{window}'] = buy_ratio
    
    # === LOSS AVERSION INDICATORS ===
    early_close = []
    for idx in range(len(trader_df)):
        if idx > 0:
            prev_profit = trader_df.loc[idx-1, 'profit_loss']
            curr_profit = trader_df.loc[idx, 'profit_loss']
            if prev_profit > 0 and curr_profit > prev_profit:
                early_close.append(1)
            else:
                early_close.append(0)
        else:
            early_close.append(0)
    df.loc[trader_indices, 'early_close_indicator'] = early_close
    
    # === REVENGE TRADING INDICATORS ===
    qty_after_loss = []
    for idx in range(len(trader_df)):
        if idx > 0 and trader_df.loc[idx-1, 'profit_loss'] < 0:
            qty_ratio = trader_df.loc[idx, 'quantity'] / (trader_df.loc[idx-1, 'quantity'] + 1e-6)
            qty_after_loss.append(qty_ratio)
        else:
            qty_after_loss.append(0.0)
    df.loc[trader_indices, 'qty_after_loss'] = qty_after_loss

print("✓ Features engineered")

# List all features
features = [col for col in df.columns if col not in 
            ['timestamp', 'asset', 'side', 'trader_type', 'profit_loss', 'exit_price', 'entry_price']]

print(f"\n📋 Using {len(features)} features:")
print(f"   {', '.join(features)}\n")

# Prepare data
X = df[features].fillna(0).replace([np.inf, -np.inf], 0)
y = df['trader_type']

# Train-test split with stratification
print("Train-test split...")
X_train, X_test, y_train, y_test = train_test_split(
    X, y, 
    test_size=0.2, 
    random_state=42,
    stratify=y
)
print(f"✓ Training: {len(X_train)} samples")
print(f"✓ Test: {len(X_test)} samples")

# Compute class weights to handle imbalance
sample_weights = compute_sample_weight('balanced', y_train)

def main() -> None:
    calm = pl.read_csv("../../datasets/patched/calm_trader.csv").with_columns(
        pl.lit(0).alias("trader_type")
    )
    loss_averse = pl.read_csv("../../datasets/patched/loss_averse_trader.csv").with_columns(
        pl.lit(1).alias("trader_type")
    )
    overtrader = pl.read_csv("../../datasets/patched/overtrader.csv").with_columns(
        pl.lit(2).alias("trader_type")
    )
    revenge = pl.read_csv("../../datasets/patched/revenge_trader.csv").with_columns(
        pl.lit(3).alias("trader_type")
    )

    all_df = pl.concat([calm, loss_averse, overtrader, revenge], how="vertical")
    x_matrix, y_values = prepare_features(all_df)
    x_train, x_test, y_train, y_test = train_test_split(x_matrix, y_values, test_ratio=0.2, seed=42)

# Evaluate
print("\n📊 Results:")
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
print(f"✓ Accuracy: {accuracy:.4f} ({accuracy*100:.2f}%)")

print("\nClassification Report:")
print(classification_report(y_test, y_pred, 
                          target_names=['calm_trader', 'loss_averse_trader', 'overtrader', 'revenge_trader']))

# Feature importance
print("\n🎯 Top 20 Important Features:")
importance_df = pd.DataFrame({
    'feature': features,
    'importance': model.feature_importances_
}).sort_values('importance', ascending=False)
print(importance_df.head(20).to_string(index=False))

    booster.save_model("trader_classifier.json")
    print("Saved trader_classifier.json")


if __name__ == "__main__":
    main()
