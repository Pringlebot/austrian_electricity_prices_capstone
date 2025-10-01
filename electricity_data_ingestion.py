"""
Electricity Data Ingestion Pipeline
Automated consolidation of Austrian day-ahead electricity prices (2015-2025)
"""

import pandas as pd
import numpy as np
import glob
from pathlib import Path
from datetime import datetime
import warnings

# Suppress pandas warnings
warnings.filterwarnings('ignore')

def setup_pandas_options():
    """Configure pandas display options for better data inspection."""
    pd.set_option('display.max_columns', None)
    pd.set_option('display.max_rows', 100)  
    pd.set_option('display.width', None)

def discover_electricity_files(data_path, file_pattern="Day Ahead Preise_M15_*_English.csv"):
    """
    Discover all electricity price files in the specified directory.
    
    Args:
        data_path (Path): Path to raw data directory
        file_pattern (str): Glob pattern for file matching
    
    Returns:
        list: List of dictionaries with file info (year, filename, path)
    """
    pattern_path = str(data_path / file_pattern)
    found_files = glob.glob(pattern_path)
    
    file_info = []
    for file_path in found_files:
        filename = Path(file_path).name
        # Extract year from filename (between M15_ and _English)
        year = filename.split('M15_')[1].split('_English')[0]
        file_info.append({
            'year': int(year),
            'filename': filename,
            'path': file_path
        })
    
    # Sort chronologically
    return sorted(file_info, key=lambda x: x['year'])

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

def load_all_electricity_files(file_info):
    """
    Load all electricity files with automatic error handling.
    
    Args:
        file_info (list): List of file dictionaries from discover_electricity_files
    
    Returns:
        dict: Dictionary with year as key, (dataframe, metadata) as value
    """
    loaded_files = {}
    
    for file_dict in file_info:
        year = file_dict['year']
        file_path = file_dict['path']
        
        try:
            # Try UTF-8 first, fall back to cp1252
            try:
                df = pd.read_csv(file_path, encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, encoding='cp1252')
            
            # Clean missing values with quality control output
            print(f"  Processing missing values for {year}...")
            df_clean, missing_patterns = standardize_missing_values(df, show_quality_control=True)
            
            # Convert time columns to datetime
            time_columns = [col for col in df_clean.columns if 'time' in col.lower()]
            for col in time_columns:
                df_clean[col] = pd.to_datetime(df_clean[col], errors='coerce')
            
            # Create metadata
            metadata = {
                'year': year,
                'filename': file_dict['filename'],
                'rows': len(df_clean),
                'columns': list(df_clean.columns),
                'price_columns': [col for col in df_clean.columns if 'price' in col.lower() or 'EUR' in col],
                'missing_patterns_found': missing_patterns,
                'date_range': (df_clean.iloc[:, 0].min(), df_clean.iloc[:, 0].max()) if len(df_clean) > 0 else (None, None)
            }
            
            loaded_files[year] = (df_clean, metadata)
            
        except Exception as e:
            loaded_files[year] = (None, {'error': str(e)})
    
    return loaded_files

def extract_hybrid_price_columns(df, year, metadata):
    """
    Extract correct price columns based on year and rename consistently.
    
    Args:
        df (DataFrame): Raw electricity data
        year (int): Year of the data
        metadata (dict): Metadata about the file
    
    Returns:
        DataFrame: DataFrame with standardized price columns
    """
    if df is None:
        return None
    
    df_prices = df.copy()
    df_prices['price_exaa_raw'] = np.nan
    df_prices['price_mc_raw'] = np.nan
    
    # Extract EXAA prices (2015-2022)
    if 2015 <= year <= 2022:
        exaa_col = None
        for col in df.columns:
            if 'EXAA' in col and 'EUR' in col:
                exaa_col = col
                break
        
        if exaa_col:
            df_prices['price_exaa_raw'] = pd.to_numeric(df[exaa_col], errors='coerce')
    
    # Extract MC Auction prices (2020-2025)
    if 2020 <= year <= 2025:
        mc_col = None
        for col in df.columns:
            if 'MC Auction' in col and 'EUR' in col:
                mc_col = col
                break
        
        if mc_col:
            df_prices['price_mc_raw'] = pd.to_numeric(df[mc_col], errors='coerce')
    
    # Keep only essential columns: time + prices
    time_col = df.columns[0]
    essential_columns = [time_col, 'price_exaa_raw', 'price_mc_raw']
    
    df_final = df_prices[essential_columns].copy()
    df_final.rename(columns={time_col: 'timestamp'}, inplace=True)
    
    return df_final

def create_time_aggregations(df):
    """
    Create daily, weekly, and monthly aggregations from 15-minute data.
    
    Args:
        df (DataFrame): DataFrame with timestamp and price columns
    
    Returns:
        dict: Dictionary with 'daily', 'weekly', 'monthly' DataFrames
    """
    if df is None or len(df) == 0:
        return {'daily': None, 'weekly': None, 'monthly': None}
    
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df_indexed = df.set_index('timestamp')
    
    aggregations = {}
    
    # Daily aggregation
    daily = df_indexed.resample('D').agg({
        'price_exaa_raw': ['mean', 'count'],
        'price_mc_raw': ['mean', 'count']
    })
    daily.columns = ['price_exaa_mean', 'price_exaa_count', 'price_mc_mean', 'price_mc_count']
    daily['date'] = daily.index.date
    daily['aggregation_level'] = 'daily'
    aggregations['daily'] = daily.reset_index(drop=True)
    
    # Weekly aggregation (ISO weeks, Monday start)
    weekly = df_indexed.resample('W-MON').agg({
        'price_exaa_raw': ['mean', 'count'],
        'price_mc_raw': ['mean', 'count']
    })
    weekly.columns = ['price_exaa_mean', 'price_exaa_count', 'price_mc_mean', 'price_mc_count']
    weekly['date'] = weekly.index.date
    weekly['aggregation_level'] = 'weekly'
    aggregations['weekly'] = weekly.reset_index(drop=True)
    
    # Monthly aggregation (first of month)
    monthly = df_indexed.resample('MS').agg({
        'price_exaa_raw': ['mean', 'count'],
        'price_mc_raw': ['mean', 'count']
    })
    monthly.columns = ['price_exaa_mean', 'price_exaa_count', 'price_mc_mean', 'price_mc_count']
    monthly['date'] = monthly.index.date
    monthly['aggregation_level'] = 'monthly'
    aggregations['monthly'] = monthly.reset_index(drop=True)
    
    return aggregations

def transform_to_long_format(aggregated_data_dict):
    """
    Transform aggregated data to final long format with all required columns.
    
    Args:
        aggregated_data_dict (dict): Dictionary of aggregated DataFrames by year
    
    Returns:
        DataFrame: Final long-format DataFrame
    """
    all_data = []
    
    for year, agg_data in aggregated_data_dict.items():
        if agg_data is None:
            continue
            
        for level in ['daily', 'weekly', 'monthly']:
            df = agg_data[level]
            if df is None or len(df) == 0:
                continue
            
            # Convert date to datetime for calculations
            df['date'] = pd.to_datetime(df['date'])
            
            # Add time components
            df['year'] = df['date'].dt.year
            df['month'] = df['date'].dt.month  
            df['quarter'] = df['date'].dt.quarter
            df['week'] = df['date'].dt.isocalendar().week
            df['month_name'] = df['date'].dt.month_name()
            
            # Round prices to integers
            df['price_exaa_mean'] = df['price_exaa_mean'].round().astype('Int64')
            df['price_mc_auction_mean'] = df['price_mc_mean'].round().astype('Int64')
            
            # Rename count columns
            df['price_count_exaa'] = df['price_exaa_count']
            df['price_count_mc'] = df['price_mc_count']
            
            # Calculate data completeness
            expected_intervals = {
                'daily': 96,
                'weekly': 672,
                'monthly': 2976
            }
            
            total_count = df['price_count_exaa'].fillna(0) + df['price_count_mc'].fillna(0)
            df['data_completeness'] = (total_count / expected_intervals[level] * 100).round(1)
            
            # Convert date back to string in ISO format
            df['date'] = df['date'].dt.strftime('%Y-%m-%d')
            
            # Select final columns
            final_columns = [
                'date', 'year', 'month', 'quarter', 'week', 'aggregation_level',
                'price_exaa_mean', 'price_mc_auction_mean', 
                'price_count_exaa', 'price_count_mc', 
                'data_completeness', 'month_name'
            ]
            
            df_final = df[final_columns].copy()
            all_data.append(df_final)
    
    # Concatenate all data
    if all_data:
        result = pd.concat(all_data, ignore_index=True)
        result = result.sort_values(['date', 'aggregation_level']).reset_index(drop=True)
        
        # Clean up: ensure only final columns remain
        final_columns = [
            'date', 'year', 'month', 'quarter', 'week', 'aggregation_level',
            'price_exaa_mean', 'price_mc_auction_mean', 
            'price_count_exaa', 'price_count_mc', 
            'data_completeness', 'month_name'
        ]
        
        existing_final_columns = [col for col in final_columns if col in result.columns]
        result_clean = result[existing_final_columns].copy()
        
        return result_clean
    else:
        return pd.DataFrame()

def consolidate_electricity_data(raw_data_path, output_path, verbose=True):
    """
    Main function to consolidate electricity data from raw files to final dataset.
    
    Args:
        raw_data_path (str/Path): Path to directory with raw electricity CSV files
        output_path (str/Path): Path where to save the consolidated CSV
        verbose (bool): Whether to print progress information
    
    Returns:
        DataFrame: Consolidated electricity data
    """
    raw_data_path = Path(raw_data_path)
    output_path = Path(output_path)
    
    # Setup
    setup_pandas_options()
    
    if verbose:
        print("ELECTRICITY DATA CONSOLIDATION")
        print("=" * 50)
        print(f"Raw data path: {raw_data_path}")
        print(f"Output path: {output_path}")
        print()
    
    # Step 1: Discover files
    if verbose:
        print("Step 1: Discovering files...")
    file_info = discover_electricity_files(raw_data_path)
    
    if not file_info:
        print("ERROR: No electricity files found!")
        return pd.DataFrame()
    
    if verbose:
        print(f"  Found {len(file_info)} files ({file_info[0]['year']}-{file_info[-1]['year']})")
    
    # Step 2: Load all files
    if verbose:
        print("Step 2: Loading files...")
    loaded_files = load_all_electricity_files(file_info)
    
    # Step 3: Extract price columns
    if verbose:
        print("Step 3: Extracting price columns...")
    processed_files = {}
    
    for year, (df, metadata) in loaded_files.items():
        if df is not None:
            processed_df = extract_hybrid_price_columns(df, year, metadata)
            if processed_df is not None:
                processed_files[year] = processed_df
                if verbose:
                    print(f"  {year}: {len(processed_df)} rows")
    
    # Step 4: Create aggregations
    if verbose:
        print("Step 4: Creating aggregations...")
    aggregated_files = {}
    
    for year, df in processed_files.items():
        aggregations = create_time_aggregations(df)
        aggregated_files[year] = aggregations
    
    # Step 5: Transform to long format
    if verbose:
        print("Step 5: Transforming to long format...")
    final_df = transform_to_long_format(aggregated_files)
    
    if len(final_df) > 0:
        # Save to file
        final_df.to_csv(output_path, index=False)
        
        if verbose:
            print(f"SUCCESS: {len(final_df)} rows saved to {output_path}")
            print(f"  Date range: {final_df['date'].min()} to {final_df['date'].max()}")
            print(f"  Shape: {final_df.shape}")
            print(f"  Aggregation levels: {final_df['aggregation_level'].value_counts().to_dict()}")
        
        return final_df
    else:
        print("ERROR: No data produced")
        return pd.DataFrame()

# Main execution
if __name__ == "__main__":
    # Example usage
    raw_path = Path("data/raw/day_ahead_prices")
    output_file = Path("data/processed/electricity_consolidated.csv")
    
    df = consolidate_electricity_data(raw_path, output_file)
    print(f"\nConsolidated {len(df)} rows of electricity data")