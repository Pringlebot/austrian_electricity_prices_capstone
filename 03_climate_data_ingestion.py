"""
Climate Data Ingestion Pipeline
Automated consolidation of EUROSTAT climate data (2012-2024) and merge with consolidated data

IMPORTANT: Climate data is MONTHLY ONLY - no daily or weekly rows created.
This prevents adding ~5190 empty rows to data_consolidated.csv.
Climate variables can only be used in monthly-level analyses.
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

def load_climate_data(file_path, date_column='TIME_PERIOD', delimiter=',', decimal='.'):
    """
    Load climate data and filter to relevant columns only.
    
    Args:
        file_path (str/Path): Path to climate CSV file
        date_column (str): Name of date column
        delimiter (str): CSV delimiter
        decimal (str): Decimal separator
    
    Returns:
        tuple: (dataframe, metadata)
    """
    try:
        df = pd.read_csv(file_path, delimiter=delimiter, decimal=decimal)
        
        # Filter to only relevant columns (4 of 19)
        relevant_columns = [date_column, 'indic_nrg', 'geo', 'OBS_VALUE']
        df_filtered = df[relevant_columns].copy()
        
        # Clean missing values
        df_clean, missing_patterns = standardize_missing_values(df_filtered, show_quality_control=True)
        
        # Convert date column to datetime (YYYY-MM format)
        df_clean[date_column] = pd.to_datetime(df_clean[date_column], format='%Y-%m')
        
        # Create metadata
        metadata = {
            'filename': Path(file_path).name,
            'rows': len(df_clean),
            'columns': list(df_clean.columns),
            'geographic_entities': df_clean['geo'].unique().tolist(),
            'indicators': df_clean['indic_nrg'].unique().tolist(),
            'missing_patterns_found': missing_patterns,
            'date_range': (df_clean[date_column].min(), df_clean[date_column].max()) if len(df_clean) > 0 else (None, None)
        }
        
        return df_clean, metadata
        
    except Exception as e:
        return None, {'error': str(e)}

def pivot_climate_by_geography(df, geo_code, date_column='TIME_PERIOD'):
    """
    Pivot climate data for a specific geography from long to wide format.
    Converts indic_nrg values (CDD, HDD) from rows to columns.
    
    Args:
        df (DataFrame): Climate data in long format
        geo_code (str): Geographic code to filter ('AT' or 'EU27_2020')
        date_column (str): Name of date column
    
    Returns:
        DataFrame: Pivoted climate data with CDD and HDD as columns
    """
    df_geo = df[df['geo'] == geo_code].copy()
    
    df_pivoted = df_geo.pivot(
        index=date_column,
        columns='indic_nrg',
        values='OBS_VALUE'
    )
    
    df_pivoted.reset_index(inplace=True)
    df_pivoted.columns.name = None
    
    return df_pivoted

def merge_climate_geographies(df_austria, df_eu, date_column='TIME_PERIOD'):
    """
    Merge Austria and EU climate data horizontally.
    
    Args:
        df_austria (DataFrame): Pivoted Austria climate data
        df_eu (DataFrame): Pivoted EU climate data
        date_column (str): Name of date column for merge
    
    Returns:
        DataFrame: Merged climate data with both AT and EU columns
    """
    df_austria_renamed = df_austria.copy()
    df_austria_renamed.rename(columns={'CDD': 'CDD_AT', 'HDD': 'HDD_AT'}, inplace=True)
    
    df_eu_renamed = df_eu.copy()
    df_eu_renamed.rename(columns={'CDD': 'CDD_EU', 'HDD': 'HDD_EU'}, inplace=True)
    
    df_merged = pd.merge(df_austria_renamed, df_eu_renamed, on=date_column, how='outer')
    
    return df_merged

def standardize_climate_column_names(df, date_column='TIME_PERIOD'):
    """
    Standardize climate column names with climate_ prefix.
    
    Args:
        df (DataFrame): Merged climate data
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
            new_name = f"climate_{new_name}"
            rename_map[col] = new_name
    
    df_renamed.rename(columns=rename_map, inplace=True)
    return df_renamed

def transform_climate_to_long_format(df, date_column='TIME_PERIOD'):
    """
    Transform climate data to long format.
    IMPORTANT: Only creates MONTHLY rows (no daily/weekly).
    
    Args:
        df (DataFrame): Climate data with standardized columns
        date_column (str): Name of date column
    
    Returns:
        DataFrame: Climate data in long format (monthly only)
    """
    df_long = df.copy()
    
    df_long[date_column] = pd.to_datetime(df_long[date_column])
    
    df_long['year'] = df_long[date_column].dt.year
    df_long['month'] = df_long[date_column].dt.month
    df_long['quarter'] = df_long[date_column].dt.quarter
    df_long['week'] = df_long[date_column].dt.isocalendar().week
    df_long['month_name'] = df_long[date_column].dt.month_name()
    df_long['aggregation_level'] = 'monthly'
    
    df_long['date'] = df_long[date_column].apply(lambda x: x.replace(day=1).strftime('%Y-%m-%d'))
    
    # Convert all climate columns to float64
    climate_columns = [col for col in df_long.columns if col.startswith('climate_')]
    for col in climate_columns:
        df_long[col] = df_long[col].astype('float64')
    
    # Select final columns
    base_columns = ['date', 'year', 'month', 'quarter', 'week', 'aggregation_level', 'month_name']
    final_columns = base_columns + climate_columns
    
    df_final = df_long[final_columns].copy()
    
    return df_final

def merge_climate_with_consolidated_data(climate_df, consolidated_file_path, output_dir):
    """
    Merge climate data with existing consolidated data.
    
    Args:
        climate_df (DataFrame): Climate dataset in long format (monthly only)
        consolidated_file_path (str/Path): Path to data_consolidated.csv
        output_dir (Path): Directory for final output
    
    Returns:
        DataFrame: Merged dataset with climate data added
    """
    consolidated_path = Path(consolidated_file_path)
    
    if not consolidated_path.exists():
        print(f"ERROR: Consolidated file not found at {consolidated_path}")
        return pd.DataFrame()
    
    try:
        consolidated_df = pd.read_csv(consolidated_path)
        
        merged_df = pd.merge(
            consolidated_df, 
            climate_df, 
            on=['date', 'aggregation_level'], 
            how='outer',
            suffixes=('', '_climate')
        )
        
        # Handle duplicate columns
        duplicate_cols = ['year', 'month', 'quarter', 'week', 'month_name']
        for col in duplicate_cols:
            climate_col = f"{col}_climate"
            if climate_col in merged_df.columns:
                merged_df[col] = merged_df[col].fillna(merged_df[climate_col])
                merged_df.drop(climate_col, axis=1, inplace=True)
        
        merged_df = merged_df.sort_values(['date', 'aggregation_level']).reset_index(drop=True)
        
        final_path = output_dir / "data_consolidated.csv"
        merged_df.to_csv(final_path, index=False, na_rep='')
        
        return merged_df
        
    except Exception as e:
        print(f"ERROR during merge: {e}")
        return pd.DataFrame()

def consolidate_climate_data(raw_file_path, consolidated_file_path, output_dir, verbose=True):
    """
    Main function to consolidate climate data and merge with existing data.
    
    Args:
        raw_file_path (str/Path): Path to raw climate CSV file
        consolidated_file_path (str/Path): Path to data_consolidated.csv
        output_dir (str/Path): Directory for outputs
        verbose (bool): Whether to print progress information
    
    Returns:
        DataFrame: Final consolidated dataset with climate data
    """
    raw_file_path = Path(raw_file_path)
    output_dir = Path(output_dir)
    
    setup_pandas_options()
    
    if verbose:
        print("="*60)
        print("CLIMATE DATA CONSOLIDATION AND MERGE")
        print("="*60)
        print("IMPORTANT: Climate data is MONTHLY ONLY")
        print("No daily or weekly rows will be created")
        print(f"Climate file: {raw_file_path}")
        print(f"Consolidated file: {consolidated_file_path}")
        print(f"Output directory: {output_dir}")
        print()
    
    # Step 1: Load data
    if verbose:
        print("Step 1: Loading and cleaning climate data...")
    
    df, metadata = load_climate_data(raw_file_path)
    
    if df is None:
        print(f"ERROR: {metadata['error']}")
        return pd.DataFrame()
    
    if verbose:
        print(f"  SUCCESS: {metadata['rows']} rows loaded")
        print(f"  Date range: {metadata['date_range'][0].strftime('%Y-%m')} to {metadata['date_range'][1].strftime('%Y-%m')}")
        print(f"  Geographic entities: {metadata['geographic_entities']}")
    
    # Step 2: Pivot Austria and EU
    if verbose:
        print("\nStep 2: Pivoting Austria and EU data...")
    
    climate_austria = pivot_climate_by_geography(df, 'AT')
    climate_eu = pivot_climate_by_geography(df, 'EU27_2020')
    
    if verbose:
        print(f"  Austria: {len(climate_austria)} rows")
        print(f"  EU: {len(climate_eu)} rows")
    
    # Step 3: Merge geographies
    if verbose:
        print("\nStep 3: Merging Austria and EU...")
    
    climate_merged = merge_climate_geographies(climate_austria, climate_eu)
    
    if verbose:
        print(f"  SUCCESS: {len(climate_merged)} rows, {len(climate_merged.columns)} columns")
    
    # Step 4: Standardize names
    if verbose:
        print("\nStep 4: Standardizing column names...")
    
    climate_standardized = standardize_climate_column_names(climate_merged)
    
    if verbose:
        climate_cols = [col for col in climate_standardized.columns if col.startswith('climate_')]
        print(f"  Climate columns: {climate_cols}")
    
    # Step 5: Transform to long format
    if verbose:
        print("\nStep 5: Transforming to long format (monthly only)...")
    
    climate_long = transform_climate_to_long_format(climate_standardized)
    
    if len(climate_long) > 0:
        if verbose:
            print(f"  SUCCESS: {len(climate_long)} monthly rows")
        
        # Save climate dataset
        climate_path = output_dir / "climate_consolidated.csv"
        climate_long.to_csv(climate_path, index=False, na_rep='')
        
        if verbose:
            print(f"  Climate dataset saved: {climate_path}")
    else:
        print("ERROR: No climate data produced")
        return pd.DataFrame()
    
    # Step 6: Merge with consolidated data
    if verbose:
        print("\nStep 6: Merging with consolidated data...")
    
    final_df = merge_climate_with_consolidated_data(climate_long, consolidated_file_path, output_dir)
    
    if len(final_df) > 0:
        if verbose:
            print(f"SUCCESS: Final merged dataset created")
            print(f"  Output: {output_dir / 'data_consolidated.csv'}")
            print(f"  Shape: {final_df.shape}")
            print(f"  Date range: {final_df['date'].min()} to {final_df['date'].max()}")
            
            climate_cols = [col for col in final_df.columns if col.startswith('climate_')]
            print(f"  Climate columns added: {len(climate_cols)}")
        
        return final_df
    else:
        print("ERROR: Merge failed")
        return pd.DataFrame()

if __name__ == "__main__":
    # Example usage
    raw_climate = Path("data/raw/climate/nrg_chddr2_m__custom_17979334_linear_2_0.csv")
    consolidated_file = Path("data/processed/data_consolidated.csv")
    output_directory = Path("data/processed")
    
    final_df = consolidate_climate_data(raw_climate, consolidated_file, output_directory)
    
    if len(final_df) > 0:
        print(f"\nSuccessfully consolidated climate data")
        print(f"Final dataset now contains: Electricity + Carbon + Climate")
    else:
        print("\nConsolidation failed")