"""
Carbon Prices Data Ingestion Pipeline
Automated consolidation of EU ETS carbon prices (2015-2025) and merge with electricity data
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')

def setup_pandas_options():
    """Configure pandas display options for better data inspection."""
    pd.set_option('display.max_columns', None)
    pd.set_option('display.max_rows', 100)  
    pd.set_option('display.width', None)

def standardize_missing_values(df, additional_missing=None, show_quality_control=True):
    """
    Convert various missing value representations to pandas NaN.
    
    Args:
        df (DataFrame): Input dataframe
        additional_missing (list): Extra missing indicators beyond defaults
        show_quality_control (bool): Whether to display quality control output
    
    Returns:
        DataFrame: Dataframe with standardized missing values
        dict: Report of found missing patterns
    """
    missing_indicators = [
        'N/A', 'n/a', 'NA', 'na',
        '', '-', '--', '---',
        'NULL', 'null', 'Null',
        'NaN', 'nan', '#N/A'
    ]
    
    if additional_missing:
        missing_indicators.extend(additional_missing)
    
    if show_quality_control:
        print("\nMISSING VALUES STANDARDIZATION - QUALITY CONTROL:")
        print("-" * 55)
        print("Missing indicators standardized:")
        print("  ", ', '.join([f"'{ind}'" for ind in missing_indicators]))
        print()
    
    found_patterns = {}
    df_clean = df.copy()
    
    for col in df_clean.columns:
        original_nulls = df_clean[col].isnull().sum()
        df_clean[col] = df_clean[col].replace(missing_indicators, np.nan)
        new_nulls = df_clean[col].isnull().sum()
        converted_count = new_nulls - original_nulls
        
        if converted_count > 0:
            found_patterns[col] = {
                'original_nulls': original_nulls,
                'converted_missing': converted_count,
                'total_nulls': new_nulls
            }
    
    if show_quality_control:
        if found_patterns:
            print("CONVERSION RESULTS BY COLUMN:")
            for col, pattern in found_patterns.items():
                print(f"  {col}:")
                print(f"    Original nulls: {pattern['original_nulls']}")
                print(f"    Converted missing: {pattern['converted_missing']}")
                print(f"    Total nulls: {pattern['total_nulls']}")
        else:
            print("No missing value patterns found for conversion")
        print("-" * 55)
    
    return df_clean, found_patterns

def load_carbon_data(file_path, date_column='Date', delimiter=',', decimal='.'):
    """
    Load carbon prices dataset with proper settings.
    
    Args:
        file_path (str/Path): Path to carbon CSV file
        date_column (str): Name of date column
        delimiter (str): CSV delimiter
        decimal (str): Decimal separator
    
    Returns:
        tuple: (dataframe, metadata)
    """
    try:
        df = pd.read_csv(file_path, delimiter=delimiter, decimal=decimal)
        
        df_clean, missing_patterns = standardize_missing_values(df, show_quality_control=True)
        
        df_clean[date_column] = pd.to_datetime(df_clean[date_column], format='%Y-%m-%d')
        
        metadata = {
            'filename': Path(file_path).name,
            'rows': len(df_clean),
            'columns': list(df_clean.columns),
            'price_columns': [col for col in df_clean.columns if any(x in col for x in ['Primary Market', 'Secondary Market', 'Exchange rate'])],
            'missing_patterns_found': missing_patterns,
            'date_range': (df_clean[date_column].min(), df_clean[date_column].max()) if len(df_clean) > 0 else (None, None)
        }
        
        return df_clean, metadata
        
    except Exception as e:
        return None, {'error': str(e)}

def consolidate_carbon_structural_break(df, date_column='Date'):
    """
    Handle structural break through temporal consolidation.
    Break occurs at 2019-01-07: (<2019) columns before, (>2018) columns after.
    
    Args:
        df (DataFrame): Raw carbon data with structural break
        date_column (str): Name of date column
    
    Returns:
        DataFrame: Data with consolidated columns
    """
    df_consolidated = df.copy()
    
    # Remove junk columns
    junk_columns = []
    for col in df_consolidated.columns:
        col_stripped = str(col).strip()
        if (col_stripped == '' or 
            col_stripped in [' ', '.1', '1', 'Unnamed'] or 
            col_stripped.startswith('Unnamed:') or
            df_consolidated[col].isna().all()):
            junk_columns.append(col)
    
    if junk_columns:
        df_consolidated.drop(junk_columns, axis=1, inplace=True)
    
    # Define structural break date
    break_date = '2019-01-07'
    df_consolidated['temp_date'] = pd.to_datetime(df_consolidated[date_column])
    
    # Exchange rate EUR/USD consolidation
    eur_usd_before = 'Exchange rate EUR/USD(<2019)'
    eur_usd_after = 'Exchange rate EUR/USD(>2018)'
    
    if eur_usd_before in df_consolidated.columns and eur_usd_after in df_consolidated.columns:
        df_consolidated['Exchange rate EUR/USD'] = np.where(
            df_consolidated['temp_date'] < break_date,
            df_consolidated[eur_usd_before],
            df_consolidated[eur_usd_after]
        )
        df_consolidated.drop([eur_usd_before, eur_usd_after], axis=1, inplace=True)
    
    # Primary Market consolidation  
    primary_before = 'Primary Market(<2019)'
    primary_after = 'Primary Market(>2018)'
    
    if primary_before in df_consolidated.columns and primary_after in df_consolidated.columns:
        df_consolidated['Primary Market'] = np.where(
            df_consolidated['temp_date'] < break_date,
            df_consolidated[primary_before],
            df_consolidated[primary_after]
        )
        df_consolidated.drop([primary_before, primary_after], axis=1, inplace=True)
    
    # Secondary Market (only exists after break)
    secondary_after = 'Secondary Market(>2018)'
    
    if secondary_after in df_consolidated.columns:
        df_consolidated['Secondary Market'] = df_consolidated[secondary_after]
        df_consolidated.drop([secondary_after], axis=1, inplace=True)
    
    # Drop unwanted columns
    columns_to_drop = []
    for col in df_consolidated.columns:
        if ('Exchange rate EUR/EUR' in str(col) or 
            'Market Currency' in str(col) or
            col == 'temp_date'):
            columns_to_drop.append(col)
    
    if columns_to_drop:
        df_consolidated.drop(columns_to_drop, axis=1, inplace=True)
    
    return df_consolidated

def standardize_carbon_column_names(df, date_column='Date'):
    """
    Standardize column names with carbonprices_ prefix.
    
    Args:
        df (DataFrame): Data with consolidated columns
        date_column (str): Name of date column to preserve
    
    Returns:
        DataFrame: Data with standardized column names
    """
    df_renamed = df.copy()
    rename_map = {}
    
    for col in df.columns:
        if col == date_column:
            continue
        else:
            new_name = col.lower()
            new_name = new_name.replace(' ', '_')
            new_name = new_name.replace('/', '_')
            new_name = new_name.replace('-', '_')
            new_name = new_name.replace('(', '').replace(')', '')
            new_name = new_name.replace('>', '')
            new_name = f"carbonprices_{new_name}"
            rename_map[col] = new_name
    
    df_renamed.rename(columns=rename_map, inplace=True)
    return df_renamed

def create_carbon_aggregations(df, date_col='Date'):
    """
    Create daily, weekly, and monthly aggregations for carbon data.
    Different handling for price columns (Int64) vs exchange rates (float64).
    
    Args:
        df (DataFrame): Carbon data with standardized columns
        date_col (str): Name of date column
    
    Returns:
        dict: Dictionary with 'daily', 'weekly', 'monthly' DataFrames
    """
    if df is None or len(df) == 0:
        return {'daily': None, 'weekly': None, 'monthly': None}
    
    df_work = df.copy()
    df_work[date_col] = pd.to_datetime(df_work[date_col])
    df_indexed = df_work.set_index(date_col)
    
    carbon_columns = [col for col in df_indexed.columns if col.startswith('carbonprices_')]
    price_columns = [col for col in carbon_columns if 'market' in col.lower()]
    exchange_rate_columns = [col for col in carbon_columns if 'exchange_rate' in col.lower()]
    
    # Convert to numeric upfront
    for col in carbon_columns:
        df_indexed[col] = pd.to_numeric(df_indexed[col], errors='coerce')
    
    aggregations = {}
    
    # Daily aggregation
    daily = df_indexed.copy()
    daily['date'] = daily.index.date
    daily['aggregation_level'] = 'daily'
    
    for col in price_columns:
        daily[col] = daily[col].round().astype('Int64')
    for col in exchange_rate_columns:
        daily[col] = daily[col].astype('float64')
    
    aggregations['daily'] = daily.reset_index(drop=True)
    
    # Weekly aggregation
    weekly = df_indexed[carbon_columns].resample('W-MON').mean()
    weekly['date'] = weekly.index.date
    weekly['aggregation_level'] = 'weekly'
    
    for col in price_columns:
        weekly[col] = weekly[col].round().astype('Int64')
    for col in exchange_rate_columns:
        weekly[col] = weekly[col].astype('float64')
    
    aggregations['weekly'] = weekly.reset_index(drop=True)
    
    # Monthly aggregation
    monthly = df_indexed[carbon_columns].resample('MS').mean()
    monthly['date'] = monthly.index.date
    monthly['aggregation_level'] = 'monthly'
    
    for col in price_columns:
        monthly[col] = monthly[col].round().astype('Int64')
    for col in exchange_rate_columns:
        monthly[col] = monthly[col].astype('float64')
    
    aggregations['monthly'] = monthly.reset_index(drop=True)
    
    return aggregations

def transform_carbon_to_long_format(aggregations_dict):
    """
    Transform carbon aggregations to long format.
    
    Args:
        aggregations_dict (dict): Dictionary of aggregated carbon DataFrames
    
    Returns:
        DataFrame: Carbon data in long format
    """
    all_data = []
    
    for level in ['daily', 'weekly', 'monthly']:
        df = aggregations_dict[level]
        if df is None or len(df) == 0:
            continue
        
        df['date'] = pd.to_datetime(df['date'])
        
        df['year'] = df['date'].dt.year
        df['month'] = df['date'].dt.month
        df['quarter'] = df['date'].dt.quarter
        df['week'] = df['date'].dt.isocalendar().week
        df['month_name'] = df['date'].dt.month_name()
        
        carbon_columns = [col for col in df.columns if col.startswith('carbonprices_')]
        
        if carbon_columns:
            non_null_counts = df[carbon_columns].notna().sum(axis=1)
            max_possible = len(carbon_columns)
            df['data_completeness'] = (non_null_counts / max_possible * 100).round(1)
        else:
            df['data_completeness'] = pd.Series(0.0, index=df.index)
        
        df['date'] = df['date'].dt.strftime('%Y-%m-%d')
        
        base_columns = ['date', 'year', 'month', 'quarter', 'week', 'aggregation_level', 'month_name']
        carbon_columns = [col for col in df.columns if col.startswith('carbonprices_')]
        other_columns = ['data_completeness']
        
        final_columns = base_columns + carbon_columns + other_columns
        existing_columns = [col for col in final_columns if col in df.columns]
        
        df_final = df[existing_columns].copy()
        all_data.append(df_final)
    
    if all_data:
        result = pd.concat(all_data, ignore_index=True)
        result = result.sort_values(['date', 'aggregation_level']).reset_index(drop=True)
        return result
    else:
        return pd.DataFrame()

def merge_carbon_with_electricity(carbon_df, electricity_file_path, output_dir):
    """
    Merge carbon data with existing electricity data.
    
    Args:
        carbon_df (DataFrame): Carbon dataset in long format
        electricity_file_path (str/Path): Path to electricity_consolidated.csv
        output_dir (Path): Directory for final output
    
    Returns:
        DataFrame: Merged dataset
    """
    electricity_path = Path(electricity_file_path)
    
    if not electricity_path.exists():
        print(f"ERROR: Electricity file not found at {electricity_path}")
        return pd.DataFrame()
    
    try:
        electricity_df = pd.read_csv(electricity_path)
        
        merged_df = pd.merge(
            electricity_df, 
            carbon_df, 
            on=['date', 'aggregation_level'], 
            how='outer',
            suffixes=('', '_carbon')
        )
        
        # Handle duplicate columns
        duplicate_cols = ['year', 'month', 'quarter', 'week', 'month_name', 'data_completeness']
        for col in duplicate_cols:
            carbon_col = f"{col}_carbon"
            if carbon_col in merged_df.columns:
                merged_df[col] = merged_df[col].fillna(merged_df[carbon_col])
                merged_df.drop(carbon_col, axis=1, inplace=True)
        
        merged_df = merged_df.sort_values(['date', 'aggregation_level']).reset_index(drop=True)
        
        final_path = output_dir / "data_consolidated.csv"
        merged_df.to_csv(final_path, index=False, na_rep='')
        
        return merged_df
        
    except Exception as e:
        print(f"ERROR during merge: {e}")
        return pd.DataFrame()

def consolidate_carbon_data(raw_file_path, electricity_file_path, output_dir, verbose=True):
    """
    Main function to consolidate carbon data and merge with electricity data.
    
    Args:
        raw_file_path (str/Path): Path to raw carbon CSV file
        electricity_file_path (str/Path): Path to electricity_consolidated.csv
        output_dir (str/Path): Directory for outputs
        verbose (bool): Whether to print progress information
    
    Returns:
        DataFrame: Final consolidated dataset (electricity + carbon)
    """
    raw_file_path = Path(raw_file_path)
    output_dir = Path(output_dir)
    
    setup_pandas_options()
    
    if verbose:
        print("="*60)
        print("CARBON DATA CONSOLIDATION AND MERGE")
        print("="*60)
        print(f"Carbon file: {raw_file_path}")
        print(f"Electricity file: {electricity_file_path}")
        print(f"Output directory: {output_dir}")
        print()
    
    # Step 1: Load data
    if verbose:
        print("Step 1: Loading and cleaning carbon data...")
    
    df, metadata = load_carbon_data(raw_file_path)
    
    if df is None:
        print(f"ERROR: {metadata['error']}")
        return pd.DataFrame()
    
    if verbose:
        print(f"  SUCCESS: {metadata['rows']} rows loaded")
        print(f"  Date range: {metadata['date_range'][0]} to {metadata['date_range'][1]}")
    
    # Step 2: Handle structural break
    if verbose:
        print("\nStep 2: Handling structural break...")
    
    df_consolidated = consolidate_carbon_structural_break(df)
    
    if verbose:
        print(f"  SUCCESS: {len(df_consolidated.columns)} columns after consolidation")
    
    # Step 3: Standardize names
    if verbose:
        print("\nStep 3: Standardizing column names...")
    
    df_standardized = standardize_carbon_column_names(df_consolidated)
    
    if verbose:
        print(f"  SUCCESS: {list(df_standardized.columns)}")
    
    # Step 4: Create aggregations
    if verbose:
        print("\nStep 4: Creating aggregations...")
    
    aggregations = create_carbon_aggregations(df_standardized)
    
    if verbose:
        for level, agg_df in aggregations.items():
            if agg_df is not None:
                print(f"  {level}: {len(agg_df)} periods")
    
    # Step 5: Transform to long format
    if verbose:
        print("\nStep 5: Transforming to long format...")
    
    carbon_df = transform_carbon_to_long_format(aggregations)
    
    if len(carbon_df) > 0:
        if verbose:
            print(f"  SUCCESS: {len(carbon_df)} rows in carbon dataset")
        
        # Save carbon dataset
        carbon_path = output_dir / "carbon_consolidated.csv"
        carbon_df.to_csv(carbon_path, index=False, na_rep='')
        
        if verbose:
            print(f"  Carbon dataset saved: {carbon_path}")
    else:
        print("ERROR: No carbon data produced")
        return pd.DataFrame()
    
    # Step 6: Merge with electricity
    if verbose:
        print("\nStep 6: Merging with electricity data...")
    
    final_df = merge_carbon_with_electricity(carbon_df, electricity_file_path, output_dir)
    
    if len(final_df) > 0:
        if verbose:
            print(f"SUCCESS: Final merged dataset created")
            print(f"  Output: {output_dir / 'data_consolidated.csv'}")
            print(f"  Shape: {final_df.shape}")
            print(f"  Date range: {final_df['date'].min()} to {final_df['date'].max()}")
        
        return final_df
    else:
        print("ERROR: Merge failed")
        return pd.DataFrame()

if __name__ == "__main__":
    # Example usage
    raw_carbon = Path("data/raw/carbon_prices/icap-graph-price-data-2015-01-01-2025-09-12.csv")
    electricity_file = Path("data/processed/electricity_consolidated.csv")
    output_directory = Path("data/processed")
    
    final_df = consolidate_carbon_data(raw_carbon, electricity_file, output_directory)
    
    if len(final_df) > 0:
        print(f"\nSuccessfully consolidated {len(final_df)} rows of combined electricity and carbon data")
    else:
        print("\nConsolidation failed")