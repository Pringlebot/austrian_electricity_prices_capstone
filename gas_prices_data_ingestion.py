"""
Gas Prices Data Ingestion Pipeline
Processes Austrian Energy Agency gas price data (OEGPI, monthly)

Output: gas_consolidated.csv + merges with data_consolidated.csv
"""

import pandas as pd
import openpyxl
import numpy as np
from pathlib import Path
from datetime import datetime
import warnings

# =============================================================================
# CONFIGURATION
# =============================================================================

GAS_FILE_NAME = "oegpi_data.xlsx"
DATE_COLUMN = "Datum"
SKIPROWS = list(range(10))  # Skip rows 0-9 (metadata and jpg)

# German month abbreviations mapping
GERMAN_MONTHS = {
    'Jan': '01', 'Feb': '02', 'Mrz': '03', 'Apr': '04',
    'Mai': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
    'Sep': '09', 'Okt': '10', 'Nov': '11', 'Dez': '12'
}

# Column mapping: Source column name → Target column name
COLUMN_MAPPING = {
    'Datum': 'date',
    'Monat': 'oegpi_month',
    'Quartal': 'oegpi_quarter',
    'Saison': 'oegpi_season',
    'Jahr': 'oegpi_year'
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

def parse_german_date(date_str):
    """
    Parse German date format YYYY-Mmm to datetime.
    
    Args:
        date_str (str): Date string in format "2020-Jan"
    
    Returns:
        datetime: Parsed datetime object (first day of month)
    """
    if pd.isna(date_str):
        return pd.NaT
    
    try:
        # Split year and month abbreviation
        year, month_abbr = str(date_str).split('-')
        
        # Lookup month number from German abbreviation
        month_num = GERMAN_MONTHS.get(month_abbr)
        
        if month_num is None:
            print(f"WARNING: Unknown month abbreviation '{month_abbr}' in date '{date_str}'")
            return pd.NaT
        
        # Construct datetime (first day of month)
        return pd.to_datetime(f"{year}-{month_num}-01")
        
    except Exception as e:
        print(f"ERROR parsing date '{date_str}': {e}")
        return pd.NaT

# =============================================================================
# DATA LOADING
# =============================================================================

def load_gas_data(file_path, skiprows, column_mapping):
    """
    Load gas prices data from Excel and select relevant columns.
    
    Args:
        file_path (str/Path): Path to gas prices Excel file
        skiprows (list): Row indices to skip (metadata rows)
        column_mapping (dict): Mapping of source to target column names
    
    Returns:
        tuple: (dataframe, metadata)
    """
    try:
        # Load Excel file with header skip
        df = pd.read_excel(file_path, skiprows=skiprows)
        
        # Strip whitespace from column names (Excel often has trailing spaces)
        df.columns = df.columns.str.strip()
        
        print(f"INITIAL DATA LOAD:")
        print(f"  Original shape: {df.shape}")
        print(f"  Rows after header skip: {len(df)}")
        print(f"  Total columns available: {len(df.columns)}")
        print()
        
        # Select only relevant columns (date + 4 price columns)
        source_columns = list(column_mapping.keys())
        
        print(f"COLUMN SELECTION:")
        print(f"  Selecting {len(source_columns)} of {len(df.columns)} columns")
        print()
        
        # Column selection
        df_filtered = df[source_columns].copy()
        
        print(f"After column selection: {df_filtered.shape}")
        print()
        
        # Parse German dates BEFORE cleaning missing values
        print("DATE PARSING:")
        print(f"  Parsing German date format (YYYY-Mmm)")
        
        df_filtered[DATE_COLUMN] = df_filtered[DATE_COLUMN].apply(parse_german_date)
        
        print(f"  Date parsing complete")
        print()
        
        # Clean missing values BEFORE renaming
        df_clean, missing_patterns = standardize_missing_values(df_filtered, show_quality_control=True)
        
        # Rename columns to standardized names
        df_clean.rename(columns=column_mapping, inplace=True)
        
        print(f"\nCOLUMN RENAMING:")
        print(f"  Renamed {len(column_mapping)} columns with oegpi_ prefix")
        print()
        
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
        print(f"ERROR loading gas data: {e}")
        return None, {'error': str(e)}

# =============================================================================
# DATA TRANSFORMATION
# =============================================================================

def convert_gas_data_types(df):
    """
    Convert gas price columns to appropriate numeric types.
    Gas prices are kept as float64 (decimals needed for price precision).
    
    Args:
        df (DataFrame): Gas data with oegpi_ prefixed columns
    
    Returns:
        DataFrame: Data with converted types
    """
    df_converted = df.copy()
    
    print("DATA TYPE CONVERSION:")
    print("-" * 40)
    
    # Get all gas price columns (exclude date column)
    gas_columns = [col for col in df_converted.columns if col.startswith('oegpi_')]
    
    print(f"Converting {len(gas_columns)} gas price columns to numeric:")
    
    for col in gas_columns:
        # Convert to numeric (handles any string values)
        df_converted[col] = pd.to_numeric(df_converted[col], errors='coerce')
        
        # Keep as float64 (prices need decimal precision)
        df_converted[col] = df_converted[col].astype('float64')
    
    print(f"  All columns converted to float64")
    print()
    print("NOTE: Gas prices kept as float64 for decimal precision")
    
    return df_converted

def transform_gas_to_long_format(df, date_column='date'):
    """
    Transform gas price data to long format.
    IMPORTANT: Only creates MONTHLY rows (no daily/weekly as per architecture decision).
    
    Args:
        df (DataFrame): Gas price data with standardized columns
        date_column (str): Name of date column
    
    Returns:
        DataFrame: Gas price data in long format (monthly only)
    """
    print("\nTRANSFORMING TO LONG FORMAT:")
    print("-" * 40)
    print("ARCHITECTURAL NOTE: Creating MONTHLY rows only")
    print("No daily or weekly rows will be created for gas price data")
    print("Consistent with climate and production data architecture")
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
    gas_columns = [col for col in df_long.columns if col.startswith('oegpi_')]
    final_columns = base_columns + gas_columns
    
    df_final = df_long[final_columns].copy()
    
    print(f"FINAL STRUCTURE:")
    print(f"  Rows: {len(df_final)} (monthly only)")
    print(f"  Columns: {len(df_final.columns)}")
    print(f"  Gas price variables: {len(gas_columns)}")
    print(f"  Date range: {df_final['date'].min()} to {df_final['date'].max()}")
    print()
    
    return df_final

# =============================================================================
# DATA PERSISTENCE
# =============================================================================

def save_gas_dataset(df, output_dir, filename="gas_consolidated.csv"):
    """
    Save gas prices dataset as separate validation sample.
    
    Args:
        df (DataFrame): Final gas prices dataset
        output_dir (Path): Directory for outputs
        filename (str): Output filename
    
    Returns:
        Path: Path to saved file
    """
    if df is None or len(df) == 0:
        print("No gas data to save!")
        return None
    
    output_path = output_dir / filename
    df.to_csv(output_path, index=False)
    
    print(f"GAS PRICES DATASET SAVED:")
    print(f"  Path: {output_path}")
    print(f"  Rows: {len(df)}")
    print(f"  Columns: {len(df.columns)}")
    print(f"  Aggregation level: {df['aggregation_level'].unique()}")
    print(f"  Date range: {df['date'].min()} to {df['date'].max()}")
    
    # Show gas price columns summary
    gas_columns = [col for col in df.columns if col.startswith('oegpi_')]
    print(f"  Gas price variables: {len(gas_columns)}")
    
    return output_path

def merge_gas_with_consolidated_data(gas_df, consolidated_file_path, output_dir):
    """
    Merge gas price data with existing consolidated data.
    
    Args:
        gas_df (DataFrame): Gas price dataset in long format (monthly only)
        consolidated_file_path (str/Path): Path to data_consolidated.csv
        output_dir (Path): Directory for final output
    
    Returns:
        DataFrame: Merged dataset with gas price data added
    """
    consolidated_path = Path(consolidated_file_path)
    
    if not consolidated_path.exists():
        print(f"ERROR: Consolidated file not found at {consolidated_path}")
        return pd.DataFrame()
    
    print("MERGING GAS PRICES WITH CONSOLIDATED DATA:")
    print("-" * 50)
    
    try:
        # Load existing consolidated data
        consolidated_df = pd.read_csv(consolidated_path)
        
        print(f"Existing consolidated data loaded:")
        print(f"  Shape: {consolidated_df.shape}")
        print(f"  Aggregation levels: {consolidated_df['aggregation_level'].value_counts().to_dict()}")
        print()
        
        print(f"Gas price data to merge:")
        print(f"  Shape: {gas_df.shape}")
        print(f"  Aggregation levels: {gas_df['aggregation_level'].value_counts().to_dict()}")
        print(f"  Date range: {gas_df['date'].min()} to {gas_df['date'].max()}")
        print()
        
        # Merge on date and aggregation_level
        merged_df = pd.merge(
            consolidated_df, 
            gas_df, 
            on=['date', 'aggregation_level'], 
            how='outer',  # Keep all rows from both datasets
            suffixes=('', '_gas')
        )
        
        print(f"After merge:")
        print(f"  Shape: {merged_df.shape}")
        print()
        
        # Handle duplicate columns from merge
        duplicate_cols = ['year', 'month', 'quarter', 'week', 'month_name']
        for col in duplicate_cols:
            gas_col = f"{col}_gas"
            if gas_col in merged_df.columns:
                merged_df[col] = merged_df[col].fillna(merged_df[gas_col])
                merged_df.drop(gas_col, axis=1, inplace=True)
                print(f"  Resolved duplicate: {col}")
        
        # Sort by date and aggregation level
        merged_df = merged_df.sort_values(['date', 'aggregation_level']).reset_index(drop=True)
        
        # Save merged dataset
        final_path = output_dir / "data_consolidated.csv"
        merged_df.to_csv(final_path, index=False)
        
        print(f"\nFINAL CONSOLIDATED DATASET:")
        print(f"  Saved to: {final_path}")
        print(f"  Final shape: {merged_df.shape}")
        print(f"  Date range: {merged_df['date'].min()} to {merged_df['date'].max()}")
        print(f"  Aggregation levels: {merged_df['aggregation_level'].value_counts().to_dict()}")
        print()
        
        # Show which columns are gas-specific
        gas_columns = [col for col in merged_df.columns if col.startswith('oegpi_')]
        print(f"Gas price columns added ({len(gas_columns)}):")
        for col in gas_columns:
            non_null = merged_df[col].notna().sum()
            print(f"  {col}: {non_null} non-null values")
        
        return merged_df
        
    except Exception as e:
        print(f"ERROR during merge: {e}")
        return pd.DataFrame()

# =============================================================================
# MAIN PIPELINE
# =============================================================================

def consolidate_gas_data(raw_file, consolidated_file, output_dir):
    """
    Main pipeline to consolidate gas price data.
    
    Args:
        raw_file (Path): Path to raw gas prices Excel file
        consolidated_file (Path): Path to existing data_consolidated.csv
        output_dir (Path): Directory for processed outputs
    
    Returns:
        DataFrame: Final consolidated dataset with gas price data
    """
    print("="*70)
    print("GAS PRICES DATA CONSOLIDATION PIPELINE")
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
    gas_df, metadata = load_gas_data(raw_file, SKIPROWS, COLUMN_MAPPING)
    
    if gas_df is None:
        print(f"Pipeline failed: {metadata.get('error', 'Unknown error')}")
        return pd.DataFrame()
    
    # Step 2: Convert data types
    print("\nSTEP 2: CONVERT DATA TYPES")
    print("-" * 70)
    gas_converted = convert_gas_data_types(gas_df)
    
    # Step 3: Transform to long format
    print("\nSTEP 3: TRANSFORM TO LONG FORMAT")
    print("-" * 70)
    gas_long = transform_gas_to_long_format(gas_converted)
    
    # Step 4: Save standalone file
    print("\nSTEP 4: SAVE STANDALONE FILE")
    print("-" * 70)
    save_gas_dataset(gas_long, output_dir)
    
    # Step 5: Merge with consolidated data
    print("\nSTEP 5: MERGE WITH CONSOLIDATED DATA")
    print("-" * 70)
    final_df = merge_gas_with_consolidated_data(gas_long, consolidated_file, output_dir)
    
    print("\n" + "="*70)
    print("PIPELINE COMPLETE")
    print("="*70)
    print(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if len(final_df) > 0:
        print("✓ Gas price data successfully integrated")
        print(f"✓ Final dataset: {final_df.shape[0]} rows × {final_df.shape[1]} columns")
    else:
        print("✗ Pipeline failed - check errors above")
    
    return final_df

# =============================================================================
# SCRIPT ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    # Setup paths
    raw_file = Path("data/raw/gas_prices/oegpi_data.xlsx")
    consolidated_file = Path("data/processed/data_consolidated.csv")
    output_dir = Path("data/processed")
    
    # Run pipeline
    final_df = consolidate_gas_data(raw_file, consolidated_file, output_dir)