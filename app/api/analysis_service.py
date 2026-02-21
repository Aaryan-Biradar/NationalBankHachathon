import numpy as np
import pandas as pd
import polars as pl
import xgboost as xgb

from . import state
from .data_service import get_last_numeric_value
from .schemas import BiasDetectionResult, MetricsRecord, TraderAnalysis

TRADER_TYPES = {
    0: "calm_trader",
    1: "loss_averse_trader",
    2: "overtrader",
    3: "revenge_trader",
}

RECOMMENDATIONS_MAP = {
    "calm_trader": [
        "You show disciplined trading patterns - maintain your consistent approach",
        "Your risk management is solid - continue with current position sizing",
        "Focus on optimizing entry/exit timing for better profit capture",
    ],
    "loss_averse_trader": [
        "You tend to close winning positions too quickly while holding losses",
        "Implement fixed take-profit levels to let winners run",
        "Use stop-loss orders to systematically manage losing trades",
        "Keep detailed trade journal to identify emotional decision patterns",
    ],
    "overtrader": [
        "You're trading too frequently - set daily/weekly trade limits",
        "Implement a cooling-off period between trades to reduce impulsivity",
        "Review transaction costs - they're eating into your profits",
        "Quality over quantity: focus on high-conviction setups only",
    ],
    "revenge_trader": [
        "You show signs of revenge trading after losses - take breaks",
        "Implement a mandatory cooling-off period after consecutive losses",
        "Practice mindfulness and emotional regulation before trading",
        "Use automation to enforce pre-planned risk management rules",
    ],
}

BIAS_DESCRIPTIONS = {
    "calm_trader": "Disciplined and consistent trading patterns with good emotional control",
    "loss_averse_trader": "Tendency to close winning trades quickly but hold losing positions longer",
    "overtrader": "Frequent trading, potentially due to over-confidence or lack of discipline",
    "revenge_trader": "Increased activity and risk after losses, indicating emotional decisions",
}


def detect_overtrading(df: pl.DataFrame) -> TraderAnalysis:
    return predict_trader_type_analysis(df)


def detect_loss_aversion(df: pl.DataFrame) -> TraderAnalysis:
    return predict_trader_type_analysis(df)


def detect_revenge_trading(df: pl.DataFrame) -> TraderAnalysis:
    return predict_trader_type_analysis(df)


def predict_trader_type_analysis(df: pl.DataFrame) -> TraderAnalysis:
    """
    Predict trader type using XGBoost model.
    Integrates test.py logic for feature engineering.
    """
    if state.model is None or len(df) == 0:
        return {
            "type": "Trader Type Prediction",
            "confidence_score": 0.0,
            "description": "Unable to make prediction - model not loaded or insufficient data.",
            "recommendations": [],
            "all_bias_scores": {
                "calm_trader": 0.0,
                "loss_averse_trader": 0.0,
                "overtrader": 0.0,
                "revenge_trader": 0.0,
            },
        }

    try:
        # Convert Polars to Pandas for easier feature engineering (matching test.py)
        pdf = df.to_pandas()
        
        # Data cleaning - matching test.py exactly
        pdf["timestamp"] = pd.to_datetime(pdf["timestamp"], errors="coerce")
        
        # Handle missing profit_loss
        mask_null_pl = pdf["profit_loss"].isna()
        if mask_null_pl.any():
            pdf.loc[mask_null_pl, "profit_loss"] = (
                pdf.loc[mask_null_pl, "exit_price"] - pdf.loc[mask_null_pl, "entry_price"]
            )
        
        # Drop rows with missing critical columns
        critical_cols = ["quantity", "side", "timestamp", "entry_price", "exit_price"]
        pdf = pdf.dropna(subset=critical_cols)
        
        # Remove balance column
        if "balance" in pdf.columns:
            pdf = pdf.drop("balance", axis=1)
        
        # Sort by timestamp
        pdf = pdf.sort_values("timestamp").reset_index(drop=True)
        
        if len(pdf) == 0:
            return {
                "type": "Trader Type Prediction",
                "confidence_score": 0.0,
                "description": "Insufficient data after cleaning.",
                "recommendations": [],
                "all_bias_scores": {
                    "calm_trader": 0.0,
                    "loss_averse_trader": 0.0,
                    "overtrader": 0.0,
                    "revenge_trader": 0.0,
                },
            }
        
        # === BASIC FEATURES - matching test.py ===
        pdf["side_encoded"] = (pdf["side"] == "BUY").astype(int)
        pdf["profit_loss_actual"] = pdf["profit_loss"]
        pdf["is_profit"] = (pdf["profit_loss"] > 0).astype(int)
        pdf["loss_amount"] = pdf["profit_loss"].apply(lambda x: abs(x) if x < 0 else 0)
        
        pdf["price_range"] = pdf["exit_price"] - pdf["entry_price"]
        pdf["price_range_pct"] = (
            (pdf["price_range"] / (pdf["entry_price"].abs() + 1e-6)) * 100
        )
        pdf["trade_value"] = pdf["quantity"] * pdf["entry_price"]
        
        # === WINDOWED BEHAVIORAL PATTERNS - matching test.py (windows: 20, 50) ===
        window_sizes = [20, 50]
        
        for window in window_sizes:
            pdf[f"win_rate_{window}"] = (
                pdf["is_profit"].rolling(window, min_periods=1).mean().fillna(0.5)
            )
            pdf[f"avg_qty_{window}"] = (
                pdf["quantity"].rolling(window, min_periods=1).mean().fillna(pdf["quantity"].mean())
            )
            pdf[f"qty_volatility_{window}"] = (
                pdf["quantity"].rolling(window, min_periods=1).std().fillna(0)
            )
            pdf[f"qty_max_{window}"] = (
                pdf["quantity"].rolling(window, min_periods=1).max().fillna(0)
            )
            
            pdf[f"avg_profit_{window}"] = (
                pdf["profit_loss"].rolling(window, min_periods=1).mean().fillna(0)
            )
            pdf[f"profit_std_{window}"] = (
                pdf["profit_loss"].rolling(window, min_periods=1).std().fillna(0)
            )
            pdf[f"max_drawdown_{window}"] = (
                pdf["profit_loss"].rolling(window, min_periods=1).min().fillna(0)
            )
            
            pdf[f"buy_ratio_{window}"] = (
                pdf["side_encoded"].rolling(window, min_periods=1).mean().fillna(0.5)
            )
        
        # === LOSS AVERSION INDICATORS - matching test.py ===
        early_close = []
        for idx in range(len(pdf)):
            if idx > 0:
                prev_profit = pdf.loc[idx - 1, "profit_loss"]
                curr_profit = pdf.loc[idx, "profit_loss"]
                if prev_profit > 0 and curr_profit > prev_profit:
                    early_close.append(1)
                else:
                    early_close.append(0)
            else:
                early_close.append(0)
        pdf["early_close_indicator"] = early_close
        
        # === REVENGE TRADING INDICATORS - matching test.py ===
        qty_after_loss = []
        for idx in range(len(pdf)):
            if idx > 0 and pdf.loc[idx - 1, "profit_loss"] < 0:
                qty_ratio = pdf.loc[idx, "quantity"] / (pdf.loc[idx - 1, "quantity"] + 1e-6)
                qty_after_loss.append(qty_ratio)
            else:
                qty_after_loss.append(0.0)
        pdf["qty_after_loss"] = qty_after_loss
        
        # === PREPARE FEATURES FOR PREDICTION - matching test.py ===
        features = [
            col
            for col in pdf.columns
            if col not in ["timestamp", "asset", "side", "profit_loss", "exit_price", "entry_price"]
        ]
        
        X = pdf[features].fillna(0).replace([np.inf, -np.inf], 0)
        
        # Make predictions using the model
        predictions = state.model.predict(X)
        probabilities = state.model.predict_proba(X)
        
        print(f"🔍 Predictions generated for {len(predictions)} trades")
        print(f"   Prediction distribution: {dict(zip(*np.unique(predictions, return_counts=True)))}")
        print(f"   Probability shape: {probabilities.shape}")
        
        # Get most common trader type
        unique, counts = np.unique(predictions, return_counts=True)
        most_common_idx = unique[np.argmax(counts)]
        most_common_type = TRADER_TYPES[most_common_idx]
        confidence = np.max(probabilities, axis=1).mean()
        
        print(f"   Most common type: {most_common_type} (confidence: {confidence:.2%})")
        
        # Calculate bias scores based on prediction distribution and confidence
        # For each class: (% of trades predicted as this class) * (avg confidence for that class)
        all_bias_scores = {}
        for class_idx in range(len(TRADER_TYPES)):
            # Trades predicted as this class
            class_mask = predictions == class_idx
            if class_mask.any():
                # Percentage of trades predicted as this class
                class_percentage = class_mask.sum() / len(predictions)
                # Average confidence when predicting this class
                class_confidence = probabilities[class_mask, class_idx].mean()
                # Combined score
                score = float(class_percentage * class_confidence)
                all_bias_scores[TRADER_TYPES[class_idx]] = score
                print(f"   {TRADER_TYPES[class_idx]}: {class_percentage:.1%} trades × {class_confidence:.2%} confidence = {score:.3f}")
            else:
                all_bias_scores[TRADER_TYPES[class_idx]] = 0.0
                print(f"   {TRADER_TYPES[class_idx]}: 0% trades = 0.000")
        
        return {
            "type": f"Trader Type: {most_common_type.replace('_', ' ').title()}",
            "confidence_score": float(confidence),
            "description": BIAS_DESCRIPTIONS.get(most_common_type, "Unknown trader type"),
            "recommendations": RECOMMENDATIONS_MAP.get(most_common_type, []),
            "all_bias_scores": all_bias_scores,
        }
        
    except Exception as e:
        print(f"Error in predict_trader_type_analysis: {e}")
        import traceback
        traceback.print_exc()
        return {
            "type": "Trader Type Prediction",
            "confidence_score": 0.0,
            "description": f"Error during prediction: {str(e)}",
            "recommendations": [],
            "all_bias_scores": {
                "calm_trader": 0.0,
                "loss_averse_trader": 0.0,
                "overtrader": 0.0,
                "revenge_trader": 0.0,
            },
        }

        # Select features (must match training features)
        features = [
            col
            for col in work_df.columns
            if col not in ["timestamp", "asset", "side", "profit_loss", "exit_price", "entry_price"]
        ]
        features_matrix = (
            work_df.select(features)
            .with_columns(pl.all().cast(pl.Float64, strict=False))
            .fill_null(0.0)
            .to_numpy()
        )
        features_matrix = np.nan_to_num(features_matrix, nan=0.0, posinf=0.0, neginf=0.0)

        dmatrix = xgb.DMatrix(features_matrix)
        probabilities = state.model.predict(dmatrix)
        if probabilities.ndim == 1:
            probabilities = probabilities.reshape(-1, 1)
        predictions = np.argmax(probabilities, axis=1)

        avg_probabilities = probabilities.mean(axis=0)
        unique, counts = np.unique(predictions, return_counts=True)
        most_common_idx = unique[np.argmax(counts)]
        most_common_type = state.TRADER_TYPES[most_common_idx]

        return {
            "type": f"Trader Type: {most_common_type.replace('_', ' ').title()}",
            "confidence_score": float(avg_probabilities[most_common_idx]),
            "description": BIAS_DESCRIPTIONS.get(
                most_common_type, "Unknown trader type pattern detected"
            ),
            "recommendations": RECOMMENDATIONS_MAP.get(most_common_type, []),
            "all_bias_scores": {
                "calm_trader": float(avg_probabilities[0]),
                "loss_averse_trader": float(avg_probabilities[1]),
                "overtrader": float(avg_probabilities[2]),
                "revenge_trader": float(avg_probabilities[3]),
            },
        }

    except Exception as exc:
        return {
            "type": "Trader Type Prediction",
            "confidence_score": 0.0,
            "description": f"Error during prediction: {str(exc)}",
            "recommendations": [],
            "all_bias_scores": {
                "calm_trader": 0.0,
                "loss_averse_trader": 0.0,
                "overtrader": 0.0,
                "revenge_trader": 0.0,
            },
        }


def calculate_performance_metrics(df: pl.DataFrame) -> MetricsRecord:
    if df.height == 0:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "total_profit_loss": 0.0,
            "avg_profit_per_trade": 0.0,
            "max_drawdown": 0.0,
        }

    df_sorted = df.with_columns(
        pl.col("timestamp").cast(pl.Utf8).str.strptime(pl.Datetime, strict=False).alias("timestamp")
    ).sort("timestamp")
    start_balance = get_last_numeric_value(df_sorted.head(1), "balance")
    df_sorted = (
        df_sorted.with_columns(
            pl.col("profit_loss")
            .cast(pl.Float64, strict=False)
            .fill_null(0.0)
            .cum_sum()
            .alias("cumulative_pl")
        )
        .with_columns((pl.col("cumulative_pl") + start_balance).alias("running_balance"))
        .with_columns(pl.col("running_balance").cum_max().alias("peak_balance"))
        .with_columns((pl.col("peak_balance") - pl.col("running_balance")).alias("drawdown"))
    )

    wins = df_sorted.filter(pl.col("profit_loss").cast(pl.Float64, strict=False) > 0).height
    total_pl = float(
        df_sorted.select(
            pl.col("profit_loss").cast(pl.Float64, strict=False).fill_null(0.0).sum()
        ).item()
    )
    avg_pl = float(
        df_sorted.select(
            pl.col("profit_loss").cast(pl.Float64, strict=False).fill_null(0.0).mean()
        ).item()
    )
    max_drawdown = float(df_sorted.select(pl.col("drawdown").max()).item())

    return {
        "total_trades": df.height,
        "win_rate": round(wins / df.height * 100, 2),
        "total_profit_loss": round(total_pl, 2),
        "avg_profit_per_trade": round(avg_pl, 2),
        "max_drawdown": round(max_drawdown, 2),
    }


def build_bias_detection_results(all_bias_scores: dict[str, float]) -> list[BiasDetectionResult]:
    compact_recommendations = {
        "calm_trader": [
            "Maintain your consistent approach",
            "Continue with current position sizing",
            "Optimize entry/exit timing for better profit capture",
        ],
        "loss_averse_trader": [
            "Implement fixed take-profit levels to let winners run",
            "Use stop-loss orders to systematically manage losing trades",
            "Keep detailed trade journal to identify emotional decision patterns",
        ],
        "overtrader": [
            "Set daily/weekly trade limits",
            "Implement a cooling-off period between trades",
            "Focus on high-conviction setups only",
        ],
        "revenge_trader": [
            "Take breaks after consecutive losses",
            "Implement a mandatory cooling-off period",
            "Practice mindfulness and emotional regulation before trading",
        ],
    }

    return [
        BiasDetectionResult(
            type=bias_key.replace("_", " ").title(),
            confidence_score=float(score),
            description=BIAS_DESCRIPTIONS.get(bias_key, "Unknown bias pattern"),
            recommendations=compact_recommendations.get(bias_key, []),
        )
        for bias_key, score in all_bias_scores.items()
    ]
