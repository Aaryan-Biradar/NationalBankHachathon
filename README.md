# TradeReflect

A behavioral bias detection system for traders that identifies harmful trading patterns and provides personalized recommendations to improve trading psychology and performance.

## Overview

TradeReflect analyzes trading history to detect common behavioral biases including:
- **Overtrading** - Excessive trading frequency and position switching
- **Loss Aversion** - Letting losses run while closing winners too early
- **Revenge Trading** - Increased risk-taking after losses
- **Emotional Trading** - Time-clustered overactivity and reactive decisions

By understanding these patterns, traders can make more disciplined, psychological-aware trading decisions.

## Features

✨ **Key Capabilities:**
- CSV/Excel trading history import
- Machine learning-based bias classification
- Visual analytics and insights dashboards
- Personalized recommendations and action plans
- Real-time bias detection as new trades are added
- Behavioral finance-backed signal detection

## Project Structure

```
TradeReflect/
├── app/                      # Python backend & ML training
│   ├── api/                  # FastAPI endpoints
│   ├── mltraining/           # Model training pipelines
│   │   ├── train.py          # Model training script
│   │   ├── trader_classifier.json  # Trained bias classifier
│   │   └── test.py           # Model validation
│   └── scripts/              # Utility scripts
├── webapp/                   # React TypeScript frontend
│   ├── src/
│   │   ├── App.tsx           # Main application
│   │   ├── lib/              # Utility functions
│   │   │   ├── analysis.ts   # Bias analysis logic
│   │   │   └── parsers.ts    # Data parsing
│   │   └── types.ts          # TypeScript types
│   └── vite.config.ts        # Build configuration
├── datasets/                 # Sample trading datasets
│   ├── calm_trader.csv
│   ├── loss_averse_trader.csv
│   ├── overtrader.csv
│   └── revenge_trader.csv
└── README.md
```

## Tech Stack

**Backend:**
- Python 3.x
- FastAPI
- scikit-learn / TensorFlow (ML models)
- Pandas (data processing)

**Frontend:**
- React 18+
- TypeScript
- Vite (build tool)
- Tailwind CSS (styling)

## Architecture

### System Design

```
┌─────────────────────────────────────────────────────────────┐
│                    Web Interface                             │
│              (React + TypeScript + Vite)                     │
│                                                               │
│  - Trade Upload/Entry    - Analysis Dashboard               │
│  - Bias Visualization    - Recommendations View             │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP/REST
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI Backend                            │
│                                                               │
│  - /upload     (CSV/Excel import)                           │
│  - /analyze    (Bias detection)                             │
│  - /classify   (ML model inference)                         │
│  - /recommend  (Personalized insights)                      │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
┌─────────────────────┐    ┌──────────────────────┐
│  Rules Engine       │    │  ML Model Inference  │
│                     │    │                      │
│ - Feature Calc      │    │ - Bias Classifier    │
│ - Pattern Matching  │    │ - Confidence Scores  │
│ - Signal Detection  │    │ - Risk Assessment    │
└─────────────────────┘    └──────────────────────┘
        │                         │
        └────────────┬────────────┘
                     ▼
        ┌─────────────────────────┐
        │  Analysis Results       │
        │                         │
        │ - Bias Scores           │
        │ - Trading Patterns      │
        │ - Recommendations       │
        │ - Risk Metrics          │
        └─────────────────────────┘
```

### Data Flow

1. **Input**: User uploads CSV with trading records
2. **Parsing**: Extract and validate trade data (timestamps, prices, quantities, P&L)
3. **Feature Engineering**: Calculate behavioral indicators
4. **Classification**: ML model predicts bias categories and scores
5. **Rule-Based Detection**: Apply heuristic rules for pattern matching
6. **Analysis**: Combine ML + rules for comprehensive insights
7. **Output**: Generate visualizations, scores, and recommendations

## Machine Learning Details

### Model Architecture

**Bias Classification Model:**
- **Type**: Multi-class classifier (identifies bias categories)
- **Input Features**: ~50+ engineered features from trading data
- **Output**: Probability scores for 4 bias categories
  - Overtrading (score 0-1)
  - Loss Aversion (score 0-1)
  - Revenge Trading (score 0-1)
  - Clean/Disciplined (score 0-1)

### Feature Engineering

The model uses behavioral finance-driven features:

**Trade-Level Features:**
- Win/loss ratio
- Average winner vs average loser
- Time between trades
- Position size changes
- Holding periods
- Entry/exit efficiency

**Time-Series Features:**
- Trade frequency (trades per day/hour)
- Clustering metrics (bunched vs spread trades)
- P&L streaks (win/loss sequences)
- Volatility of trade sizing
- Recovery patterns after losses

**Portfolio Features:**
- Win rate
- Profit factor
- Sharpe ratio
- Maximum drawdown
- Consecutive losses

### Training Data

- **Dataset**: 4 labeled trader profiles across `datasets/` directory
- **Labels**: Behavioral bias classifications based on trading patterns
- **Model Format**: `trader_classifier.json` (scikit-learn or neural network serialized)
- **Training Script**: `app/mltraining/train.py`
  - Data preprocessing
  - Feature normalization
  - Train/validation split
  - Model tuning and evaluation
  - Cross-validation

### Inference Pipeline

```
Raw Trades (CSV) 
    ↓
Feature Extraction (Pandas)
    ↓
Feature Normalization
    ↓
ML Model Prediction
    ↓
Confidence Scores + Explanations
    ↓
Recommendation Engine
    ↓
User-Friendly Output
```

### Performance Metrics

The model is evaluated on:
- **Accuracy**: Correct bias classification
- **Precision/Recall**: Per-bias-category performance
- **Interpretability**: Feature importance rankings
- **Generalization**: Cross-validation on unseen data

### Model Explainability

- Feature importance scores help traders understand *why* they're classified
- Confidence thresholds filter low-certainty predictions
- Signal traceback shows specific trades triggering bias detection
- Actionable explanations translate model decisions into trader-friendly language

## Getting Started

### Prerequisites
- Python 3.8+
- Node.js 16+
- npm or yarn

### Installation

**Backend Setup:**
```bash
cd app
pip install -r requirements.txt
python mltraining/train.py  # Train bias classifier
python api/main.py          # Start API server
```

**Frontend Setup:**
```bash
cd webapp
npm install
npm run dev  # Start development server
```

### Usage

1. Open the web interface (typically `http://localhost:5173`)
2. Upload your trading CSV file or manually enter trades
3. View bias analysis and get personalized recommendations
4. Export insights and action plans

## Sample Data

Test datasets are included for different trader profiles:
- **calm_trader.csv** - Disciplined, minimal biases
- **overtrader.csv** - High trade frequency patterns
- **loss_averse_trader.csv** - Early profit-taking, long loss-holding
- **revenge_trader.csv** - Increased position sizing after losses

## Development

```bash
# Run tests
cd app
python mltraining/test.py

# Lint frontend
cd webapp
npm run lint

# Build for production
npm run build
```

## Contributing

This project was developed for the National Bank Hackathon 2026. Contributions and improvements welcome!

## License

MIT License
