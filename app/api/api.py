from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
import pandas as pd
import numpy as np
import uuid
from typing import List, Dict, Any, Optional
import io
from datetime import datetime, date
from pydantic import BaseModel
import json
import xgboost as xgb
import os

app = FastAPI(title="National Bank Bias Detector API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trader type mapping
TRADER_TYPES = {
    0: 'calm_trader',
    1: 'loss_averse_trader',
    2: 'overtrader',
    3: 'revenge_trader'
}

# In-memory storage for demo purposes
uploaded_files = {}
analysis_results = {}
model = None

def load_model():
    """Load the trained XGBoost model"""
    global model
    try:
        model_path = os.path.join(os.path.dirname(__file__), '../mltraining/trader_classifier.json')
        if os.path.exists(model_path):
            model = xgb.XGBClassifier()
            model.load_model(model_path)
            print("✓ Model loaded successfully")
        else:
            print(f"⚠ Model not found at {model_path}")
    except Exception as e:
        print(f"Error loading model: {e}")

# Pydantic models
class UploadResponse(BaseModel):
    session_id: str
    message: str

class TradeEntry(BaseModel):
    timestamp: str
    asset: str
    side: str
    quantity: float
    entry_price: float
    exit_price: float
    profit_loss: float
    balance: float

class DataResponse(BaseModel):
    session_id: str
    total_records: int
    data: List[TradeEntry]

class RangeDataResponse(DataResponse):
    date_range: Dict[str, str]

class BiasDetectionResult(BaseModel):
    type: str
    confidence_score: float
    description: str
    recommendations: List[str]

class AnalysisResponse(BaseModel):
    session_id: str
    biases_detected: List[BiasDetectionResult]
    summary: Dict[str, Any]

# What-if analysis models
class ExcludeCriteria(BaseModel):
    assets: Optional[List[str]] = None
    date_range: Optional[Dict[str, str]] = None  # {"start": "2023-01-01", "end": "2023-12-31"}
    min_loss_amount: Optional[float] = None
    max_loss_amount: Optional[float] = None
    trade_ids: Optional[List[int]] = None

class WhatIfRequest(BaseModel):
    exclude_criteria: Optional[ExcludeCriteria] = None
    output_format: str = "timeseries"  # "timeseries", "final_balance", "full_dataset"

class BalancePoint(BaseModel):
    timestamp: str
    original_balance: float
    simulated_balance: float

class WhatIfTimeseriesResponse(BaseModel):
    session_id: str
    simulation_name: str
    original_final_balance: float
    simulated_final_balance: float
    balance_change: float
    balance_timeseries: List[BalancePoint]

class WhatIfFinalBalanceResponse(BaseModel):
    session_id: str
    simulation_name: str
    original_final_balance: float
    simulated_final_balance: float
    balance_improvement: float
    improvement_percentage: float

class SimulatedTradeEntry(TradeEntry):
    included_in_simulation: bool
    simulated_balance: float

class WhatIfFullDatasetResponse(BaseModel):
    session_id: str
    simulation_name: str
    original_trades: int
    included_trades: int
    excluded_trades: int
    dataset: List[SimulatedTradeEntry]

class WhatIfDownloadRequest(BaseModel):
    exclude_criteria: ExcludeCriteria
    report_format: str = "csv"  # "csv", "xlsx"

# Additional models for enhanced features
class BiasSummary(BaseModel):
    bias_type: str
    count: int
    percentage: float

class PerformanceMetrics(BaseModel):
    total_trades: int
    win_rate: float
    total_profit_loss: float
    avg_profit_per_trade: float
    max_drawdown: float

class MetricsResponse(BaseModel):
    session_id: str
    performance_metrics: PerformanceMetrics
    bias_summary: List[BiasSummary]

# Helper functions
def parse_csv_file(file_content: bytes) -> pd.DataFrame:
    """Parse CSV file content into DataFrame"""
    try:
        df = pd.read_csv(io.StringIO(file_content.decode('utf-8')))
        return df
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing CSV: {str(e)}")

def validate_required_columns(df: pd.DataFrame) -> bool:
    """Validate that required columns are present"""
    required_columns = [
        'timestamp', 'asset', 'side', 'quantity',
        'entry_price', 'exit_price', 'profit_loss', 'balance'
    ]

    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns: {missing_columns}"
        )
    return True

def detect_overtrading(df: pd.DataFrame) -> dict:
    """Detect overtrading bias using ML model"""
    return predict_trader_type_analysis(df)

def predict_trader_type_analysis(df: pd.DataFrame) -> dict:
    """
    Use the trained XGBoost model to predict trader type and return analysis.
    Uses the improved v2 feature set (97.62% accuracy model) matching train_v2.py
    """
    if model is None or len(df) == 0:
        return {
            "type": "Trader Type Prediction",
            "confidence_score": 0.0,
            "description": "Unable to make prediction - model not loaded or insufficient data.",
            "recommendations": []
        }
    
    try:
        # Data cleaning - same as train_v2.py
        df = df.copy()
        initial_rows = len(df)
        
        # Handle missing profit_loss
        if df['profit_loss'].isna().any():
            df.loc[df['profit_loss'].isna(), 'profit_loss'] = (
                df.loc[df['profit_loss'].isna(), 'exit_price'] - 
                df.loc[df['profit_loss'].isna(), 'entry_price']
            )
        
        # Drop rows with missing critical columns
        critical_cols = ['quantity', 'side', 'timestamp', 'entry_price', 'exit_price']
        df = df.dropna(subset=critical_cols)
        
        # Drop balance column if exists
        if 'balance' in df.columns:
            df = df.drop('balance', axis=1)
        
        # Convert timestamp
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        # ============================================================================
        # FEATURE ENGINEERING - Same as train_v2.py
        # ============================================================================
        
        # === BASIC FEATURES ===
        df['hour'] = df['timestamp'].dt.hour
        df['day'] = df['timestamp'].dt.day
        df['side_encoded'] = (df['side'] == 'BUY').astype(int)
        df['profit_loss_actual'] = df['profit_loss']
        df['is_profit'] = (df['profit_loss'] > 0).astype(int)
        df['loss_amount'] = df['profit_loss'].apply(lambda x: abs(x) if x < 0 else 0)
        
        df['price_range'] = df['exit_price'] - df['entry_price']
        df['price_range_pct'] = (df['price_range'] / (df['entry_price'].abs() + 1e-6)) * 100
        df['trade_value'] = df['quantity'] * df['entry_price']
        
        # === WINDOWED BEHAVIORAL PATTERNS ===
        window_sizes = [5, 10, 20, 50]
        
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
        
        # === OVERTRADING INDICATORS ===
        time_between = df['timestamp'].diff().dt.total_seconds().fillna(0).values
        df['time_between_trades'] = time_between
        
        # ============================================================================
        # PREPARE FEATURES FOR PREDICTION
        # ============================================================================
        
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
        
        # Generate recommendations based on trader type
        recommendations_map = {
            'calm_trader': [
                "You show disciplined trading patterns - maintain your consistent approach",
                "Your risk management is solid - continue with current position sizing",
                "Focus on optimizing entry/exit timing for better profit capture"
            ],
            'loss_averse_trader': [
                "You tend to close winning positions too quickly while holding losses",
                "Implement fixed take-profit levels to let winners run",
                "Use stop-loss orders to systematically manage losing trades",
                "Keep detailed trade journal to identify emotional decision patterns"
            ],
            'overtrader': [
                "You're trading too frequently - set daily/weekly trade limits",
                "Implement a cooling-off period between trades to reduce impulsivity",
                "Review transaction costs - they're eating into your profits",
                "Quality over quantity: focus on high-conviction setups only"
            ],
            'revenge_trader': [
                "You show signs of revenge trading after losses - take breaks",
                "Implement a mandatory cooling-off period after consecutive losses",
                "Practice mindfulness and emotional regulation before trading",
                "Use automation to enforce pre-planned risk management rules"
            ]
        }
        
        trader_type_description = {
            'calm_trader': 'You maintain disciplined and consistent trading patterns with good emotional control',
            'loss_averse_trader': 'You tend to close winning trades quickly but hold losing positions longer',
            'overtrader': 'You trade frequently, potentially due to over-confidence or lack of discipline',
            'revenge_trader': 'Your trading shows increased activity and risk after losses, indicating emotional decisions'
        }
        
        return {
            "type": f"Trader Type: {most_common_type.replace('_', ' ').title()}",
            "confidence_score": float(confidence),
            "description": trader_type_description.get(most_common_type, "Unknown trader type pattern detected"),
            "recommendations": recommendations_map.get(most_common_type, [])
        }
        
    except Exception as e:
        return {
            "type": "Trader Type Prediction",
            "confidence_score": 0.0,
            "description": f"Error during prediction: {str(e)}",
            "recommendations": []
        }

def detect_loss_aversion(df: pd.DataFrame) -> dict:
    analysis = predict_trader_type_analysis(df)
    return analysis

def detect_revenge_trading(df: pd.DataFrame) -> dict:
    analysis = predict_trader_type_analysis(df)
    return analysis

def calculate_performance_metrics(df: pd.DataFrame) -> dict:
    """Calculate key performance metrics"""
    if len(df) == 0:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "total_profit_loss": 0.0,
            "avg_profit_per_trade": 0.0,
            "max_drawdown": 0.0
        }
    
    # Calculate cumulative balance to find drawdown
    df_sorted = df.sort_values('timestamp')
    df_sorted['cumulative_pl'] = df_sorted['profit_loss'].cumsum()
    df_sorted['running_balance'] = df_sorted['balance'].iloc[0] + df_sorted['cumulative_pl']
    
    # Calculate peak balance and drawdown
    df_sorted['peak_balance'] = df_sorted['running_balance'].expanding().max()
    df_sorted['drawdown'] = df_sorted['peak_balance'] - df_sorted['running_balance']
    max_drawdown = df_sorted['drawdown'].max()
    
    return {
        "total_trades": len(df),
        "win_rate": round(len(df[df['profit_loss'] > 0]) / len(df) * 100, 2),
        "total_profit_loss": round(df['profit_loss'].sum(), 2),
        "avg_profit_per_trade": round(df['profit_loss'].mean(), 2),
        "max_drawdown": round(max_drawdown, 2)
    }

def get_all_trades(session_id: str) -> List[Dict]:
    """Get all trades for a session"""
    if session_id not in uploaded_files:
        raise HTTPException(status_code=404, detail="Session ID not found")
    
    try:
        content = uploaded_files[session_id]
        df = parse_csv_file(content)
        validate_required_columns(df)
        
        # Convert DataFrame to list of dictionaries
        trades = df.to_dict('records')
        return trades
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve data: {str(e)}")

def get_trades_in_range(session_id: str, start_date: date, end_date: date) -> List[Dict]:
    """Get trades within a date range"""
    all_trades = get_all_trades(session_id)
    
    # Convert to DataFrame for easier filtering
    df = pd.DataFrame(all_trades)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Filter by date range
    start_datetime = pd.Timestamp(start_date)
    end_datetime = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    
    filtered_df = df[(df['timestamp'] >= start_datetime) & (df['timestamp'] <= end_datetime)]
    
    # Convert back to list of dictionaries
    return filtered_df.to_dict('records')

def identify_excluded_trades(df: pd.DataFrame, criteria: ExcludeCriteria) -> List[int]:
    """Identify which trades to exclude based on criteria"""
    exclude_mask = pd.Series([False] * len(df))
    
    if criteria.assets:
        exclude_mask |= df['asset'].isin(criteria.assets)
    
    if criteria.date_range:
        start_date = pd.to_datetime(criteria.date_range['start'])
        end_date = pd.to_datetime(criteria.date_range['end'])
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        exclude_mask |= (df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)
    
    if criteria.min_loss_amount is not None:
        exclude_mask |= df['profit_loss'] <= criteria.min_loss_amount
    
    if criteria.max_loss_amount is not None:
        exclude_mask |= df['profit_loss'] >= criteria.max_loss_amount
    
    if criteria.trade_ids:
        exclude_mask |= df.index.isin(criteria.trade_ids)
    
    return df[exclude_mask].index.tolist()

def calculate_simulated_balances(df: pd.DataFrame, exclude_indices: List[int]) -> pd.DataFrame:
    """Calculate balance progression with excluded trades"""
    # Create copy of dataframe
    simulated_df = df.copy()
    
    # Mark excluded trades
    simulated_df['included_in_simulation'] = ~simulated_df.index.isin(exclude_indices)
    
    # Set profit/loss to 0 for excluded trades
    simulated_df.loc[~simulated_df['included_in_simulation'], 'profit_loss'] = 0
    
    # Recalculate balance with adjusted P&L
    simulated_df = simulated_df.sort_values('timestamp')
    simulated_df['simulated_cumulative_pl'] = simulated_df['profit_loss'].cumsum()
    simulated_df['simulated_balance'] = (
        simulated_df['balance'].iloc[0] + 
        simulated_df['simulated_cumulative_pl']
    )
    
    return simulated_df

def generate_simulation_name(criteria: ExcludeCriteria) -> str:
    """Generate descriptive name for simulation"""
    if criteria.assets:
        return f"Exclude {', '.join(criteria.assets)} trades"
    elif criteria.min_loss_amount is not None:
        return f"Exclude losses below ${criteria.min_loss_amount}"
    elif criteria.max_loss_amount is not None:
        return f"Exclude gains above ${criteria.max_loss_amount}"
    elif criteria.date_range:
        return f"Exclude trades from {criteria.date_range['start']} to {criteria.date_range['end']}"
    elif criteria.trade_ids:
        return f"Exclude {len(criteria.trade_ids)} specific trades"
    else:
        return "Custom what-if simulation"

@app.post("/upload/trade-history", response_model=UploadResponse, 
          summary="Upload Trading History", 
          description="Upload a CSV file containing trading history for analysis")
async def upload_trade_history(file: UploadFile = File(...)):
    """
    Upload trading history CSV file
    Required columns: timestamp, asset, side, quantity, entry_price, exit_price, profit_loss, balance
    """
    session_id = str(uuid.uuid4())

    # Read file content
    content = await file.read()

    # Store file content (in production, save to disk/database)
    uploaded_files[session_id] = content

    return UploadResponse(
        session_id=session_id,
        message=f"Trade history uploaded successfully. Session ID: {session_id}"
    )

@app.get("/data/{session_id}", response_model=DataResponse,
         summary="Get All Trading Data",
         description="Retrieve all trading records from the uploaded file for a given session")
async def get_all_trading_data(session_id: str):
    """
    Retrieve all trading records from the uploaded file for a given session
    """
    trades = get_all_trades(session_id)
    
    return DataResponse(
        session_id=session_id,
        total_records=len(trades),
        data=[TradeEntry(**trade) for trade in trades]
    )

@app.get("/data/{session_id}/range", response_model=RangeDataResponse,
         summary="Get Trading Data by Date Range",
         description="Fetch trading records within a specified date range for a given session")
async def get_trading_data_by_range(
    session_id: str,
    start_date: date = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: date = Query(..., description="End date in YYYY-MM-DD format")
):
    """
    Fetch trading records within a specified date range for a given session
    """
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="Start date must be before or equal to end date")
    
    trades = get_trades_in_range(session_id, start_date, end_date)
    
    return RangeDataResponse(
        session_id=session_id,
        total_records=len(trades),
        date_range={
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        },
        data=[TradeEntry(**trade) for trade in trades]
    )

@app.get("/metrics/{session_id}", response_model=MetricsResponse,
         summary="Get Performance Metrics",
         description="Calculate key performance metrics for the trading history")
async def get_performance_metrics(session_id: str):
    """
    Calculate key performance metrics for the trading history
    """
    if session_id not in uploaded_files:
        raise HTTPException(status_code=404, detail="Session ID not found")
    
    try:
        # Parse the uploaded file
        content = uploaded_files[session_id]
        df = parse_csv_file(content)
        validate_required_columns(df)
        
        # Convert timestamp column to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Calculate performance metrics
        metrics = calculate_performance_metrics(df)
        
        # Detect trader type using ML model and generate bias summary
        trader_analysis = predict_trader_type_analysis(df)
        trader_confidence = trader_analysis.get('confidence_score', 0.0)
        
        # Extract trader type from description
        trader_type_str = trader_analysis.get('type', 'Unknown').replace('Trader Type: ', '')
        
        bias_summary = [
            BiasSummary(
                bias_type=trader_type_str,
                count=len(df),
                percentage=trader_confidence * 100
            )
        ]
        
        return MetricsResponse(
            session_id=session_id,
            performance_metrics=PerformanceMetrics(**metrics),
            bias_summary=bias_summary
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Metrics calculation failed: {str(e)}")

@app.post("/what-if/{session_id}/simulate",
          summary="Run What-If Simulation",
          description="Calculate alternative balance history by excluding specified trades")
async def what_if_simulation(session_id: str, request: WhatIfRequest):
    """
    Calculate alternative balance history by excluding specified trades
    Output formats: timeseries, final_balance, full_dataset
    """
    if session_id not in uploaded_files:
        raise HTTPException(status_code=404, detail="Session ID not found")
    
    try:
        # Parse the uploaded file
        content = uploaded_files[session_id]
        df = parse_csv_file(content)
        validate_required_columns(df)
        
        # Convert timestamp column to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Identify trades to exclude
        exclude_criteria = request.exclude_criteria or ExcludeCriteria()
        exclude_indices = identify_excluded_trades(df, exclude_criteria)
        
        # Calculate simulated balances
        simulated_df = calculate_simulated_balances(df, exclude_indices)
        
        # Generate simulation name
        simulation_name = generate_simulation_name(exclude_criteria)
        
        # Format response based on output_format
        if request.output_format == "timeseries":
            # Prepare timeseries data
            timeseries_data = []
            for _, row in simulated_df.iterrows():
                timeseries_data.append(BalancePoint(
                    timestamp=row['timestamp'].isoformat(),
                    original_balance=row['balance'],
                    simulated_balance=row['simulated_balance']
                ))
            
            return WhatIfTimeseriesResponse(
                session_id=session_id,
                simulation_name=simulation_name,
                original_final_balance=df['balance'].iloc[-1] if len(df) > 0 else 0,
                simulated_final_balance=simulated_df['simulated_balance'].iloc[-1] if len(simulated_df) > 0 else 0,
                balance_change=(simulated_df['simulated_balance'].iloc[-1] if len(simulated_df) > 0 else 0) - 
                              (df['balance'].iloc[-1] if len(df) > 0 else 0),
                balance_timeseries=timeseries_data
            )
        
        elif request.output_format == "final_balance":
            original_balance = df['balance'].iloc[-1] if len(df) > 0 else 0
            simulated_balance = simulated_df['simulated_balance'].iloc[-1] if len(simulated_df) > 0 else 0
            improvement = simulated_balance - original_balance
            improvement_pct = (improvement / original_balance * 100) if original_balance != 0 else 0
            
            return WhatIfFinalBalanceResponse(
                session_id=session_id,
                simulation_name=simulation_name,
                original_final_balance=original_balance,
                simulated_final_balance=simulated_balance,
                balance_improvement=improvement,
                improvement_percentage=round(improvement_pct, 2)
            )
        
        elif request.output_format == "full_dataset":
            # Prepare full dataset with simulation info
            full_dataset = []
            for _, row in simulated_df.iterrows():
                full_dataset.append(SimulatedTradeEntry(
                    timestamp=row['timestamp'].isoformat(),
                    asset=row['asset'],
                    side=row['side'],
                    quantity=row['quantity'],
                    entry_price=row['entry_price'],
                    exit_price=row['exit_price'],
                    profit_loss=row['profit_loss'],
                    balance=row['balance'],
                    included_in_simulation=row['included_in_simulation'],
                    simulated_balance=row['simulated_balance']
                ))
            
            return WhatIfFullDatasetResponse(
                session_id=session_id,
                simulation_name=simulation_name,
                original_trades=len(df),
                included_trades=len(df) - len(exclude_indices),
                excluded_trades=len(exclude_indices),
                dataset=full_dataset
            )
        
        else:
            raise HTTPException(status_code=400, detail="Invalid output_format. Must be 'timeseries', 'final_balance', or 'full_dataset'")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"What-if simulation failed: {str(e)}")

@app.post("/what-if/{session_id}/download",
          summary="Download What-If Report",
          description="Generate downloadable report of what-if simulation")
async def download_what_if_report(session_id: str, request: WhatIfDownloadRequest):
    """
    Generate downloadable report of what-if simulation
    Report formats: csv, xlsx
    """
    if session_id not in uploaded_files:
        raise HTTPException(status_code=404, detail="Session ID not found")
    
    try:
        # Parse the uploaded file
        content = uploaded_files[session_id]
        df = parse_csv_file(content)
        validate_required_columns(df)
        
        # Convert timestamp column to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Identify trades to exclude
        exclude_indices = identify_excluded_trades(df, request.exclude_criteria)
        
        # Calculate simulated balances
        simulated_df = calculate_simulated_balances(df, exclude_indices)
        
        # Add simulation columns
        simulated_df['included_in_simulation'] = ~simulated_df.index.isin(exclude_indices)
        
        if request.report_format == "csv":
            # Convert to CSV
            csv_data = simulated_df.to_csv(index=False)
            headers = {
                'Content-Disposition': 'attachment; filename="what_if_analysis.csv"',
                'Content-Type': 'text/csv'
            }
            return Response(content=csv_data, headers=headers)
        
        elif request.report_format == "xlsx":
            # Convert to Excel
            output = io.BytesIO()
            simulated_df.to_excel(output, index=False)
            output.seek(0)
            
            headers = {
                'Content-Disposition': 'attachment; filename="what_if_analysis.xlsx"',
                'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            }
            return Response(content=output.getvalue(), headers=headers)
        
        else:
            raise HTTPException(status_code=400, detail="Invalid report_format. Must be 'csv' or 'xlsx'")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

@app.on_event("startup")
async def startup_event():
    """Load model on startup"""
    load_model()

@app.get("/analyze/{session_id}", response_model=AnalysisResponse,
         summary="Analyze Trading Behavior",
         description="Analyze uploaded trading history for behavioral biases")
async def analyze_trading_history(session_id: str):
    """
    Analyze uploaded trading history for behavioral biases
    """
    if session_id not in uploaded_files:
        raise HTTPException(status_code=404, detail="Session ID not found")

    try:
        # Parse the uploaded file
        content = uploaded_files[session_id]
        df = parse_csv_file(content)

        # Validate required columns
        validate_required_columns(df)

        # Detect trader type using ML model
        trader_type_analysis = predict_trader_type_analysis(df)

        biases_detected = [
            BiasDetectionResult(**trader_type_analysis)
        ]

        # Store results
        analysis_results[session_id] = {
            "biases_detected": biases_detected,
            "total_trades": len(df),
            "win_rate": len(df[df['profit_loss'] > 0]) / len(df) if len(df) > 0 else 0
        }

        return AnalysisResponse(
            session_id=session_id,
            biases_detected=biases_detected,
            summary={
                "total_trades": len(df),
                "win_rate": round(len(df[df['profit_loss'] > 0]) / len(df) * 100, 2) if len(df) > 0 else 0,
                "total_profit_loss": df['profit_loss'].sum() if len(df) > 0 else 0
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/health",
         summary="Health Check",
         description="Check if the API is running properly")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
