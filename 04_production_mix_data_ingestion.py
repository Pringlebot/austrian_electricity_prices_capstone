"""
Production Mix Data Ingestion Pipeline
Processes E-Control Austria electricity production mix data (monthly)

Output: production_consolidated.csv + merges with data_consolidated.csv
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import warnings

# =============================================================================
# CONFIGURATION
# =============================================================================

PRODUCTION_FILE_NAME = "el_dataset_mn.csv"
DATE_COLUMN = "Header & Timestamp"
DELIMITER = ";"
DECIMAL_SEPARATOR = ","
SKIPROWS = range(1, 14)  # Skip rows 2-14 (complex header metadata)

# Column mapping: Source column name (STRING) → Target column name
COLUMN_MAPPING = {
    'Header & Timestamp': 'date',
    '15': 'prod_gross_electricity_production',
    '16': 'prod_gross_electricity_consumption',
    '37': 'prod_hydropower_production_total',
    '38': 'prod_fossil_sk_production',
    '39': 'prod_fossil_DvfB_production',
    '40': 'prod_fossil_DvOe_production',
    '41': 'prod_fossil_gas_production',
    '42': 'prod_fossil_subtotal_production',
    '43': 'prod_renewable_bio_production',
    '44': 'prod_renewable_SoBio_production',
    '45': 'prod_other_fuels_production',
    '46': 'prod_fuel_production_total',
    '47': 'prod_wind_total',
    '48': 'prod_pv_total',
    '49': 'prod_geothermal_total',
    '51': 'prod_power_production_total',
    '57': 'prod_electricity_imports',
    '58': 'prod_electricity_exports'
}

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

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

# =============================================================================
# DATA LOADING
# =============================================================================

def load_production_data(file_path, skiprows, delimiter, column_mapping, decimal_sep):
    """
    Load production mix data and select relevant columns only.
    
    Args:
        file_path (str/Path): Path to production CSV file
        skiprows (range): Row indices to skip (complex header metadata)
        delimiter (str): File delimiter
        column_mapping (dict): Mapping of source to target column names
        decimal_sep (str): Decimal separator character
    
    Returns:
        tuple: (dataframe, metadata)
    """
    try:
        # Load dataset with header skip, encoding, and decimal separator
        df = pd.read_csv(
            file_path, 
            delimiter=delimiter, 
            skiprows=skiprows,
            decimal=decimal_sep,
            encoding='ISO-8859-1'  # Austrian data with umlauts
        )
        
        print(f"INITIAL DATA LOAD:")
        print(f"  Original shape: {df.shape}")
        print(f"  Rows after header skip: {len(df)}")
        print(f"  Total columns available: {len(df.columns)}")
        print()
        
        # Select only relevant columns (18 production variables + date)
        source_columns = list(column_mapping.keys())
        
        print(f"COLUMN SELECTION:")
        print(f"  Selecting {len(source_columns)} of {len(df.columns)} columns")
        print()
        
        # Column selection using STRING column names
        df_filtered = df[source_columns].copy()
        
        print(f"After column selection: {df_filtered.shape}")
        print()
        
        # Clean missing values BEFORE renaming
        df_clean, missing_patterns = standardize_missing_values(df_filtered, show_quality_control=True)
        
        # Rename columns to standardized names
        df_clean.rename(columns=column_mapping, inplace=True)
        
        print(f"\nCOLUMN RENAMING:")
        print(f"  Renamed {len(column_mapping)} columns with prod_ prefix")
        print()
        
        # Convert date column to datetime (format: YYYY-MM)
        df_clean['date'] = pd.to_datetime(df_clean['date'], format='%Y-%m')
        
        # Create metadata
        metadata = {
            'filename': Path(file_path).name,
            'rows': len(df_clean),
            'columns': list(df_clean.columns),
            'missing_patterns_found': missing_patterns,
            'date_range': (df_clean['date'].min(), df_clean['date'].max()) if len(df_clean) > 0 else (None, None)
        }
        
        print(f"DATA SUMMARY:")
        print(f"  Final shape: {df_clean.shape}")
        print(f"  Date range: {metadata['date_range'][0].strftime('%Y-%m-%d')} to {metadata['date_range'][1].strftime('%Y-%m-%d')}")
        print()
        
        return df_clean, metadata
        
    except Exception as e:
        print(f"ERROR loading production data: {e}")
        return None, {'error': str(e)}

# =============================================================================
# DATA TRANSFORMATION
# =============================================================================

def convert_production_data_types(df):
    """
    Convert production columns to appropriate numeric types.
    Production values are rounded to integers (Int64), which will become float64 in CSV.
    
    Args:
        df (DataFrame): Production data with prod_ prefixed columns
    
    Returns:
        DataFrame: Data with converted types
    """
    df_converted = df.copy()
    
    print("DATA TYPE CONVERSION:")
    print("-" * 40)
    
    # Get all production columns (exclude date column)
    prod_columns = [col for col in df_converted.columns if col.startswith('prod_')]
    
    print(f"Converting {len(prod_columns)} production columns to numeric:")
    
    for col in prod_columns:
        # Convert to numeric first (handles any string values)
        df_converted[col] = pd.to_numeric(df_converted[col], errors='coerce')
        
        # Round to integers
        df_converted[col] = df_converted[col].round(0)
        
        # Convert to Int64 (nullable integer, will become float64 in CSV)
        df_converted[col] = df_converted[col].astype('Int64')
    
    print(f"  All columns converted to Int64")
    print()
    print("NOTE: Int64 types will convert to float64 when saved to CSV")
    print("This is an accepted limitation - float64 is compatible with all analysis tools")
    
    return df_converted

def transform_production_to_long_format(df, date_column='date'):
    """
    Transform production data to long format.
    IMPORTANT: Only creates MONTHLY rows (no daily/weekly as per architecture decision).
    
    Args:
        df (DataFrame): Production data with standardized columns
        date_column (str): Name of date column
    
    Returns:
        DataFrame: Production data in long format (monthly only)
    """
    print("\nTRANSFORMING TO LONG FORMAT:")
    print("-" * 40)
    print("ARCHITECTURAL NOTE: Creating MONTHLY rows only")
    print("No daily or weekly rows will be created for production mix data")
    print("Consistent with climate data architecture")
    print()
    
    df_long = df.copy()
    
    # Ensure date is datetime
    df_long[date_column] = pd.to_datetime(df_long[date_column])
    
    # Add time components
    df_long['year'] = df_long[date_column].dt.year
    df_long['month'] = df_long[date_column].dt.month
    df_long['quarter'] = df_long[date_column].dt.quarter
    df_long['week'] = df_long[date_column].dt.isocalendar().week
    df_long['month_name'] = df_long[date_column].dt.month_name()
    
    # Add aggregation level - MONTHLY ONLY
    df_long['aggregation_level'] = 'monthly'
    
    # Convert date to first of month in ISO format (YYYY-MM-DD)
    df_long['date'] = df_long[date_column].apply(lambda x: x.replace(day=1).strftime('%Y-%m-%d'))
    
    # Select final columns in correct order
    base_columns = ['date', 'year', 'month', 'quarter', 'week', 'aggregation_level', 'month_name']
    prod_columns = [col for col in df_long.columns if col.startswith('prod_')]
    final_columns = base_columns + prod_columns
    
    df_final = df_long[final_columns].copy()
    
    print(f"FINAL STRUCTURE:")
    print(f"  Rows: {len(df_final)} (monthly only)")
    print(f"  Columns: {len(df_final.columns)}")
    print(f"  Production variables: {len(prod_columns)}")
    print(f"  Date range: {df_final['date'].min()} to {df_final['date'].max()}")
    print()
    
    return df_final

# =============================================================================
# DATA PERSISTENCE
# =============================================================================

def save_production_dataset(df, output_dir, filename="production_consolidated.csv"):
    """
    Save production mix dataset as separate validation sample.
    
    Args:
        df (DataFrame): Final production mix dataset
        output_dir (Path): Directory for outputs
        filename (str): Output filename
    
    Returns:
        Path: Path to saved file
    """
    if df is None or len(df) == 0:
        print("No production data to save!")
        return None
    
    output_path = output_dir / filename
    df.to_csv(output_path, index=False, na_rep='')
    
    print(f"PRODUCTION MIX DATASET SAVED:")
    print(f"  Path: {output_path}")
    print(f"  Rows: {len(df)}")
    print(f"  Columns: {len(df.columns)}")
    print(f"  Aggregation level: {df['aggregation_level'].unique()}")
    print(f"  Date range: {df['date'].min()} to {df['date'].max()}")
    
    # Show production columns summary
    prod_columns = [col for col in df.columns if col.startswith('prod_')]
    print(f"  Production variables: {len(prod_columns)}")
    
    return output_path

def merge_production_with_consolidated_data(production_df, consolidated_file_path, output_dir):
    """
    Merge production mix data with existing consolidated data.
    
    Args:
        production_df (DataFrame): Production dataset in long format (monthly only)
        consolidated_file_path (str/Path): Path to data_consolidated.csv
        output_dir (Path): Directory for final output
    
    Returns:
        DataFrame: Merged dataset with production data added
    """
    consolidated_path = Path(consolidated_file_path)
    
    if not consolidated_path.exists():
        print(f"ERROR: Consolidated file not found at {consolidated_path}")
        return pd.DataFrame()
    
    print("MERGING PRODUCTION MIX WITH CONSOLIDATED DATA:")
    print("-" * 50)
    
    try:
        # Load existing consolidated data
        consolidated_df = pd.read_csv(consolidated_path)
        
        print(f"Existing consolidated data loaded:")
        print(f"  Shape: {consolidated_df.shape}")
        print(f"  Aggregation levels: {consolidated_df['aggregation_level'].value_counts().to_dict()}")
        print()
        
        print(f"Production data to merge:")
        print(f"  Shape: {production_df.shape}")
        print(f"  Aggregation levels: {production_df['aggregation_level'].value_counts().to_dict()}")
        print(f"  Date range: {production_df['date'].min()} to {production_df['date'].max()}")
        print()
        
        # Merge on date and aggregation_level
        merged_df = pd.merge(
            consolidated_df, 
            production_df, 
            on=['date', 'aggregation_level'], 
            how='outer',  # Keep all rows from both datasets
            suffixes=('', '_production')
        )
        
        print(f"After merge:")
        print(f"  Shape: {merged_df.shape}")
        print()
        
        # Handle duplicate columns from merge
        duplicate_cols = ['year', 'month', 'quarter', 'week', 'month_name']
        for col in duplicate_cols:
            production_col = f"{col}_production"
            if production_col in merged_df.columns:
                merged_df[col] = merged_df[col].fillna(merged_df[production_col])
                merged_df.drop(production_col, axis=1, inplace=True)
                print(f"  Resolved duplicate: {col}")
        
        # Sort by date and aggregation level
        merged_df = merged_df.sort_values(['date', 'aggregation_level']).reset_index(drop=True)
        
        # Save merged dataset
        final_path = output_dir / "data_consolidated.csv"
        merged_df.to_csv(final_path, index=False, na_rep='')
        
        print(f"\nFINAL CONSOLIDATED DATASET:")
        print(f"  Saved to: {final_path}")
        print(f"  Final shape: {merged_df.shape}")
        print(f"  Date range: {merged_df['date'].min()} to {merged_df['date'].max()}")
        print(f"  Aggregation levels: {merged_df['aggregation_level'].value_counts().to_dict()}")
        print()
        
        # Show which columns are production-specific
        production_columns = [col for col in merged_df.columns if col.startswith('prod_')]
        print(f"Production columns added ({len(production_columns)}):")
        for col in production_columns:
            non_null = merged_df[col].notna().sum()
            print(f"  {col}: {non_null} non-null values")
        
        return merged_df
        
    except Exception as e:
        print(f"ERROR during merge: {e}")
        return pd.DataFrame()

# =============================================================================
# MAIN PIPELINE
# =============================================================================

def consolidate_production_data(raw_file, consolidated_file, output_dir):
    """
    Main pipeline to consolidate production mix data.
    
    Args:
        raw_file (Path): Path to raw production CSV file
        consolidated_file (Path): Path to existing data_consolidated.csv
        output_dir (Path): Directory for processed outputs
    
    Returns:
        DataFrame: Final consolidated dataset with production data
    """
    print("="*70)
    print("PRODUCTION MIX DATA CONSOLIDATION PIPELINE")
    print("="*70)
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Raw File: {raw_file}")
    print(f"Consolidated File: {consolidated_file}")
    print(f"Output Directory: {output_dir}")
    print("="*70)
    print()
    
    # Step 1: Load and clean data
    print("STEP 1: LOAD AND CLEAN DATA")
    print("-" * 70)
    production_df, metadata = load_production_data(
        raw_file, 
        SKIPROWS, 
        DELIMITER, 
        COLUMN_MAPPING,
        DECIMAL_SEPARATOR
    )
    
    if production_df is None:
        print(f"Pipeline failed: {metadata.get('error', 'Unknown error')}")
        return pd.DataFrame()
    
    # Step 2: Convert data types
    print("\nSTEP 2: CONVERT DATA TYPES")
    print("-" * 70)
    production_converted = convert_production_data_types(production_df)
    
    # Step 3: Transform to long format
    print("\nSTEP 3: TRANSFORM TO LONG FORMAT")
    print("-" * 70)
    production_long = transform_production_to_long_format(production_converted)
    
    # Step 4: Save standalone file
    print("\nSTEP 4: SAVE STANDALONE FILE")
    print("-" * 70)
    save_production_dataset(production_long, output_dir)
    
    # Step 5: Merge with consolidated data
    print("\nSTEP 5: MERGE WITH CONSOLIDATED DATA")
    print("-" * 70)
    final_df = merge_production_with_consolidated_data(
        production_long, 
        consolidated_file, 
        output_dir
    )
    
    print("\n" + "="*70)
    print("PIPELINE COMPLETE")
    print("="*70)
    print(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if len(final_df) > 0:
        print("✓ Production mix data successfully integrated")
        print(f"✓ Final dataset: {final_df.shape[0]} rows × {final_df.shape[1]} columns")
    else:
        print("✗ Pipeline failed - check errors above")
    
    return final_df

# =============================================================================
# SCRIPT ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    # Setup paths
    raw_file = Path("data/raw/production_mix/el_dataset_mn.csv")
    consolidated_file = Path("data/processed/data_consolidated.csv")
    output_dir = Path("data/processed")
    
    # Run pipeline
    final_df = consolidate_production_data(raw_file, consolidated_file, output_dir)