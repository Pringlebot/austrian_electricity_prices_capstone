# austrian_electricity_prices_capstone
Paul Ringler´s Capstone Project for the 2025 "Data Practictioner" class at neuefische

Time series analysis and forecasting of European energy market prices using ARIMA/ARIMAX modeling.

## About this Project

**What this project is**
This is a **learning project** created to practice time series analysis and 
data pipeline development. The analyses are exploratory in nature and not 
intended for professional forecasting or investment decisions.

**What this project isn´t**
This project is not a thorough econometric analysis of the Austrian Energy market. While the outcome variable and its development over time will be put into historical and economic context and while input variables like gas prices, CO2 prices and available economic indicatores are used, there is no further consideration of the economic basis of the energy market.

All data sources are properly attributed. See the data documentation for details.

This project analyzes Austrian electricity day-ahead prices using ARIMA (AutoRegressive Integrated Moving Average) models, with potential extension to ARIMAX models incorporating external variables like CO2 prices, climate data, and economic indicators.

**Primary Objectives:**
- Learn and apply ARIMA/ARIMAX time series modeling
- Explore drivers of electricity price volatility
- Practice end-to-end data science project workflow
- Build reproducible data pipelines and analysis

**Scope:**
- Geographic focus: Austria (EXAA market)
- Time period: 2009-2025 (varies by dataset)
- Target variable: Day-ahead electricity prices (EUR/MWh)
- Modeling approach: Start simple (univariate ARIMA), progressively add complexity (ARIMAX with 2-3 external variables)

## Project Status

- [x] **Data Pipeline** (6/6 datasets integrated)
- [X] **Exploratory Data Analysis (EDA)**
  - [X] Visual analysis of electricity prices and exogenous Variables
  - [X] Formal time-series decomposition and Analysis of electricity price
  - [X] Correlation analysis with external variables
- [ ] **ARIMA Model Implementation**
  - [ ] Parameter tuning (p,d,q)
  - [ ] Baseline model validation
- [ ] **ARIMAX Extension**
  - [ ] Integrate 2-3 external variables (CO2 prices, climate, economic indicators)
  - [ ] Compare performance vs univariate ARIMA
- [ ] **Model Validation**
  - [ ] Time series cross-validation
  - [ ] Performance metrics (RMSE, MAE, MAPE)
- [ ] **Final Documentation & GitHub Publication**

## Data Pipeline Status

**COMPLETE** - All 6 datasets integrated into `data_consolidated.csv`

| Dataset | Source | Rows | Variables | Date Range | Frequency |
|---------|--------|------|-----------|------------|-----------|
| Electricity Prices | APG/EXAA | 3,896 daily + aggregated | 5 | 2015-2025 | 15min→daily/weekly/monthly |
| CO2 Prices | ICAP | 2,461 daily + aggregated | 3 | 2015-2025 | daily/weekly/monthly |
| Climate Data | EUROSTAT | 152 monthly | 4 | 2012-2024 | monthly only |
| Production Mix | E-Control | 187 monthly | 18 | 2010-2025 | monthly only |
| Gas Prices | AEA | 69 monthly | 4 | 2020-2025 | monthly only |
| Economic Indicators | Statistik Austria | 200 monthly | 18 | 2009-2025 | monthly only |

**Final Consolidated Dataset:**
- File: `data/processed/data_consolidated.csv`
- Shape: 4,663 rows × 59 columns
- Date Range: 2009-01-01 to 2025-09-01
- Aggregation Levels: 3,896 daily + 566 weekly + 201 monthly rows

## Data Architecture

The project uses a **three-tier aggregation architecture**:

- **Daily (3,896 rows)**: Electricity + Carbon prices only
- **Weekly (566 rows)**: Electricity + Carbon prices only  
- **Monthly (201 rows)**: All 6 datasets (52 variables)

This design reflects data availability constraints:
- High-frequency data (electricity, carbon) available at daily resolution
- Structural data (climate, production, gas, economy) available monthly only

**Implication for modeling:**
- Univariate ARIMA can use daily data (3,896 observations)
- ARIMAX with external variables limited to monthly data (201 observations)

## Variable Documentation

Complete variable documentation with sources and links is available in:
- **`meta_data_library.csv`** - Comprehensive metadata for all 59 columns

### Variable Categories

| Category | Variables | Description | Aggregation Levels |
|----------|-----------|-------------|--------------------|
| **Electricity Prices** | 5 | EXAA day-ahead prices (10:15) and MC auction prices (12:00) | Daily, Weekly, Monthly |
| **Carbon Prices** | 3 | EU ETS primary and secondary market prices | Daily, Weekly, Monthly |
| **Climate Data** | 4 | Heating/Cooling degree days (Austria & EU) | Monthly only |
| **Production Mix** | 18 | Electricity generation by source (fossil, renewable, imports/exports) | Monthly only |
| **Gas Prices** | 4 | Austrian natural gas price indices (monthly, quarterly, seasonal, annual) | Monthly only |
| **Economic Indicators** | 18 | Production indices, trade, employment, turnover | Monthly only |


### Time Series Decomposition
Multiplicative seasonal decomposition (Y = T × S × R) was selected 
after comparing residual variance with the additive model (0.17 vs 31.69). 
The multiplicative model is appropriate as seasonal variation scales 
proportionally with price level (±20% rather than constant absolute swings).

Seasonal strength analysis reveals moderate seasonality (0.36 for full 
period, 0.40 pre-shock), with December showing highest prices (96.85 EUR/MWh) 
and May lowest (57.00 EUR/MWh). The seasonal component ranges from 0.78 to 
1.15 (multiplicative factors), representing ±20% variation around trend.

However, the price shock period (2021-2023) dominates the variance structure, 
with residual volatility exceeding seasonal effects by 5x. This justifies 
the inclusion of regime dummy variables in the ARIMAX specification.
For "Stationarity Analysis" Section:
markdown#### Augmented Dickey-Fuller Test

Formal stationarity testing via ADF reveals:
- Full period (2015-2025): p=0.144, non-stationary
- Pre-shock (2015-2021): p=0.991, strongly non-stationary  
- Post-shock (2023-2025): p=0.044, stationary

The full series requires first differencing (d=1). Interestingly, the 
post-shock period is stationary, suggesting the market has stabilized 
into a "new normal" regime without persistent trend. This finding 
supports the use of regime dummies to capture structural breaks rather 
than relying solely on differencing.

PACF analysis corroborates the ADF results, with Lag 1 = 0.90 indicating 
strong autocorrelation characteristic of non-stationary series.

## Forecasting Methodology

### Temporal Scope
Due to publication delays of exogenous variables (up to 52 weeks for climate indicators), this project implements **retrospective validation** rather than 
real-time forecasting:

- **Training Period:** 2015-01 to 2024-12 (120 months)
- **Test Period:** 2025-01 to 2025-09 (9 months, out-of-sample)

### Data Availability Considerations
All exogenous variables are used without temporal lags (lag-0), as the 
validation is performed retrospectively when all 2024 data has been published. 
This approach:

1. **Measures historical relationships** between contemporaneous variables
2. **Validates model structure** on unseen data (available data points from 2025)
3. **Avoids complexity** of mixed-lag specifications for a learning project

**Note:** For operational real-time forecasts, variables would need to be 
lagged according to their publication schedules (e.g., economic indicators 
lag-2 to lag-12, gas futures available lag-0).

### Cross-Validation Strategy
Time series cross-validation with expanding window:
- 5-fold splits within training period
- Chronological ordering preserved
- No data leakage from future to past

### Key Variables for ARIMAX Modeling

**Outcome Variable:**
- `price_exaa_mean` - Average EXAA day-ahead electricity price [EUR/MWh]

**Potential External Variables (for ARIMAX):**
- `carbonprices_primary_market` - EU ETS carbon price [EUR/tCO2]
- `climate_hdd_at` - Heating degree days (Austria)
- `prod_gross_electricity_production` - Total electricity production [MWh]
- `prod_renewable_*` - Renewable energy production by source
- `econ_prod_index_industry` - Industrial production index (2021=100)
- `econ_exports_total_EUR` - Total exports [EUR]

For full variable definitions, units, sources, and links, see `meta_data_library.csv`.

## Project Structure
energy_analysis/
├── data/
│   ├── raw/                      # Original data files (not in Git)
│   │   ├── day_ahead_prices/     # EXAA electricity prices (10 CSV files)
│   │   ├── carbon_prices/        # ICAP CO2 prices
│   │   ├── climate/              # EUROSTAT climate data
│   │   ├── production_mix/       # E-Control production data
│   │   ├── gas_prices/           # AEA gas prices
│   │   └── economy/              # Statistik Austria economic indicators
│   ├── processed/                # Processed datasets
│   │   ├── data_consolidated.csv           # Final merged dataset
│   │   ├── electricity_consolidated.csv    # Individual dataset exports
│   │   ├── carbon_consolidated.csv
│   │   ├── climate_consolidated.csv
│   │   ├── production_consolidated.csv
│   │   ├── gas_consolidated.csv
│   │   └── economy_consolidated.csv
│   └── metadata/
│       └── meta_data_library.csv # Variable documentation
├── notebooks/
│   ├── 01_electricity_data_ingestion.ipynb
│   ├── 02_carbon_data_ingestion.ipynb
│   ├── 03_climate_data_ingestion.ipynb
│   ├── 04_production_mix_data_ingestion.ipynb
│   ├── 05_gas_prices_data_ingestion.ipynb
│   ├── 06_economic_data_ingestion.ipynb
│   └── [EDA and modeling notebooks to be added]
├── src/
│   ├── 01_electricity_data_ingestion.py
│   ├── 02_carbon_data_ingestion.py
│   ├── 03_climate_data_ingestion.py
│   ├── 04_production_mix_data_ingestion.py
│   ├── 05_gas_prices_data_ingestion.py
│   ├── 06_economic_data_ingestion.py
│   ├── run_all_pipelines.py              # Master pipeline script
│   └── data_consolidated_diagnostics.py  # Data quality validation
├── results/
│   ├── figures/                  # Exported visualizations
│   └── tables/                   # Exported result tables
├── docs/                         # Additional documentation
├── meta_data_library.csv         # Variable documentation (root level)
├── requirements.txt
├── README.md
└── .gitignore

## Installation & Setup

### Prerequisites
- Python 3.8+
- pip package manager
- Git

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/energy-market-analysis.git
cd energy-market-analysis
```

2. Create and activate virtual environment:

```bashpython 
-m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```
3. Install dependencies:
```
bashpip install -r requirements.txt
```
Dependencies
Core libraries:

pandas >= 2.0.0 - Data manipulation
numpy >= 1.24.0 - Numerical computing
statsmodels >= 0.14.0 - ARIMA modeling
matplotlib >= 3.7.0 - Visualization
seaborn >= 0.12.0 - Statistical visualization

Optional:

plotly - Interactive visualizations
scikit-learn - Additional metrics
jupyter - Notebook environment

## Running the Data Pipeline

### Execute All Pipelines
Run the complete data ingestion workflow:
```bash
python 
src/run_all_pipelines.py
```
This executes all 6 pipelines sequentially and generates data_consolidated.csv.

### Run Individual Pipelines
Execute pipelines independently:
```bash
python 
src/01_electricity_data_ingestion.py
python src/02_carbon_data_ingestion.py
python src/03_climate_data_ingestion.py
python src/04_production_mix_data_ingestion.py
python src/05_gas_prices_data_ingestion.py
python src/06_economic_data_ingestion.py
```

Each pipeline:

Loads raw data from data/raw/
Cleans and standardizes missing values
Creates aggregations (daily/weekly/monthly)
Merges with consolidated dataset
Saves individual dataset to data/processed/

### Verify Data Quality
Run comprehensive diagnostics:
bashpython src/data_consolidated_diagnostics.py
Validates:

## Data structure and completeness
The following were implemented:
- Missing value patterns
- Aggregation level consistency
- Data type correctness
- Architectural constraints

## Which dataset to use?

Processed Data without QoL additions:
```bash
data_consolidated.csv
```

Data finalized with QoL additions:
```bash
data_finalized.csv
```
Additions include:
- additional datetime object column for date: "date_dt"



## Data Sources & Licenses
All datasets are from public sources with appropriate usage permissions:
SourceOrganizationLicenseLinkElectricity PricesAPG/EXAAPermission grantedAPG TransparencyCO2 PricesICAPPermission grantedICAP Allowance Price ExplorerClimate DataEUROSTATOpen DataEUROSTAT DatabaseProduction MixE-Control AustriaOpen DataE-Control StatisticsGas PricesAustrian Energy AgencyOpen DataAEA Gas Price IndicesEconomic IndicatorsStatistik AustriaOpen DataStatistik Austria

Methodology
Phase 1: Exploratory Data Analysis (Upcoming)

Univariate analysis of electricity prices
Distribution analysis, outlier detection
Stationarity testing (ADF, KPSS tests)
Correlation analysis with external variables
Seasonality and trend decomposition

Phase 2: ARIMA Modeling (Upcoming)

Grid search for optimal (p,d,q) parameters
Information criteria (AIC, BIC) for model selection
Residual diagnostics (ACF, PACF, Ljung-Box)
Time series cross-validation
Performance metrics: RMSE, MAE, MAPE

Phase 3: ARIMAX Extension (Upcoming)

Select 2-3 most relevant external variables
Test variable integration (CO2 prices, climate, economic indicators)
Compare univariate vs multivariate model performance
Sensitivity analysis

Known Limitations

Data Frequency Mismatch: External variables only available monthly, limiting ARIMAX to 201 observations vs 3,896 daily observations for univariate ARIMA
Missing Data: Some variables have limited coverage:

Gas prices: Only 2020-2025 (69 months)
Some economic indicators: Sparse coverage


Temporal Alignment: Not all datasets cover the same time period (2009-2025 range varies by source)
Structural Breaks: Energy markets underwent significant changes (COVID-19, Ukraine crisis) that may affect model stability

Contributing
This is a learning project. Feedback and suggestions welcome via issues.
License
This project is licensed under the MIT License - see LICENSE file for details.
Data sources have their own licenses - see Data Sources section above.
Contact
Paul - @yourgithub
Project Link: https://github.com/yourusername/energy-market-analysis
Acknowledgments

APG/EXAA for electricity price data access
ICAP for CO2 price data access
EUROSTAT for climate data (open data)
E-Control Austria for production mix data (open data)
Austrian Energy Agency for gas price indices (open data)
Statistik Austria for economic indicators (open data)

