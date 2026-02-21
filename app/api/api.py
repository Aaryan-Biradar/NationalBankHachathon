from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
import pandas as pd
import uuid
from typing import List, Dict, Any, Optional
import io
from datetime import datetime, date
from pydantic import BaseModel
import json

app = FastAPI(title="National Bank Bias Detector API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for demo purposes
uploaded_files = {}
analysis_results = {}

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
    """Detect overtrading bias"""
    # Simple logic: more than 5 trades per day on average
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    trades_per_day = df.groupby(df['timestamp'].dt.date).size()
    avg_trades_per_day = trades_per_day.mean()

    is_overtrading = avg_trades_per_day > 5

    return {
        "type": "Overtrading",
        "confidence_score": min(avg_trades_per_day / 10, 1.0) if is_overtrading else 0.0,
        "description": f"You're averaging {avg_trades_per_day:.1f} trades per day." if is_overtrading else "Trading frequency appears normal.",
        "recommendations": [
            "Set daily trade limit of 3-5 trades",
            "Implement a cooling-off period between trades",
            "Review transaction costs impact on profitability"
        ] if is_overtrading else []
    }

def detect_loss_aversion(df: pd.DataFrame) -> dict:
    """Detect loss aversion bias"""
    winning_trades = df[df['profit_loss'] > 0]
    losing_trades = df[df['profit_loss'] < 0]

    if len(winning_trades) == 0 or len(losing_trades) == 0:
        return {
            "type": "Loss Aversion",
            "confidence_score": 0.0,
            "description": "Insufficient data to determine loss aversion pattern.",
            "recommendations": []
        }

    # Check if winners are closed too quickly vs losers held too long
    avg_win_duration = (winning_trades['exit_price'] - winning_trades['entry_price']).mean()
    avg_loss_duration = (losing_trades['exit_price'] - losing_trades['entry_price']).mean()

    is_loss_averse = avg_win_duration < abs(avg_loss_duration * 0.5)

    return {
        "type": "Loss Aversion",
        "confidence_score": 0.7 if is_loss_averse else 0.3,
        "description": "Prematurely closing winning trades while holding losing positions longer." if is_loss_averse else "Loss aversion pattern not strongly detected.",
        "recommendations": [
            "Use systematic take-profit levels",
            "Set stop-loss orders to limit downside",
            "Keep detailed trade journal to track emotional decisions"
        ] if is_loss_averse else []
    }

def detect_revenge_trading(df: pd.DataFrame) -> dict:
    """Detect revenge trading bias"""
    df_sorted = df.sort_values('timestamp')
    df_sorted['prev_profit_loss'] = df_sorted['profit_loss'].shift(1)
    df_sorted['profit_loss_diff'] = df_sorted['profit_loss'] - df_sorted['prev_profit_loss']
    
    # Look for pattern: loss followed by larger trade
    revenge_patterns = df_sorted[
        (df_sorted['prev_profit_loss'] < 0) & 
        (df_sorted['quantity'] > df_sorted['quantity'].shift(1) * 1.5)
    ]
    
    revenge_count = len(revenge_patterns)
    total_trades = len(df)
    revenge_ratio = revenge_count / total_trades if total_trades > 0 else 0
    
    is_revenge_trading = revenge_ratio > 0.1  # More than 10% of trades show revenge pattern
    
    return {
        "type": "Revenge Trading",
        "confidence_score": min(revenge_ratio * 10, 1.0),
        "description": f"{revenge_count} instances of potentially revenge trading detected." if revenge_count > 0 else "No clear revenge trading pattern found.",
        "recommendations": [
            "Take a break after consecutive losses",
            "Stick to your predetermined position sizing rules",
            "Practice mindfulness techniques before trading"
        ] if is_revenge_trading else []
    }

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
        
        # Calculate bias summary
        overtrading_result = detect_overtrading(df)
        loss_aversion_result = detect_loss_aversion(df)
        revenge_trading_result = detect_revenge_trading(df)
        
        bias_summary = [
            BiasSummary(
                bias_type="Overtrading",
                count=len(df) if overtrading_result["confidence_score"] > 0.3 else 0,
                percentage=overtrading_result["confidence_score"] * 100
            ),
            BiasSummary(
                bias_type="Loss Aversion",
                count=len(df[df['profit_loss'] < 0]) if loss_aversion_result["confidence_score"] > 0.3 else 0,
                percentage=loss_aversion_result["confidence_score"] * 100
            ),
            BiasSummary(
                bias_type="Revenge Trading",
                count=len(df) if revenge_trading_result["confidence_score"] > 0.3 else 0,
                percentage=revenge_trading_result["confidence_score"] * 100
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

        # Detect biases
        overtrading_result = detect_overtrading(df)
        loss_aversion_result = detect_loss_aversion(df)
        revenge_trading_result = detect_revenge_trading(df)

        biases_detected = [
            BiasDetectionResult(**overtrading_result),
            BiasDetectionResult(**loss_aversion_result),
            BiasDetectionResult(**revenge_trading_result)
        ]

        # Filter out biases with low confidence
        significant_biases = [bias for bias in biases_detected if bias.confidence_score > 0.3]

        # Store results
        analysis_results[session_id] = {
            "biases_detected": significant_biases,
            "total_trades": len(df),
            "win_rate": len(df[df['profit_loss'] > 0]) / len(df) if len(df) > 0 else 0
        }

        return AnalysisResponse(
            session_id=session_id,
            biases_detected=significant_biases,
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
