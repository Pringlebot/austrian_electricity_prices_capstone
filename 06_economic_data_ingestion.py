"""
Economic Indicators Data Ingestion Pipeline
Processes Statistik Austria economic indicators (monthly, 2009-2025)

Output: economy_consolidated.csv + merges with data_consolidated.csv
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import warnings

# =============================================================================
# CONFIGURATION
# =============================================================================

ECON_FILE_NAME = "table_2025-09-16_13-30-40.xlsx"
DATE_COLUMN = "Berichtszeitraum"
SKIPROWS = list(range(9)) + [10, 11]  # Skip rows 0-8 (metadata), 10-11 (wertangabe)

# Austrian German month abbreviations mapping
GERMAN_MONTHS = {
    'Jän': '01', 'Jan': '01', 'Feb': '02', 'Mär': '03', 'Mrz': '03',
    'Apr': '04', 'Mai': '05', 'Jun': '06', 'Jul': '07',
    'Aug': '08', 'Sep': '09', 'Okt': '10', 'Nov': '11', 'Dez': '12'
}

# Column mapping: Source column name → Target column name
COLUMN_MAPPING = {
    'Berichtszeitraum': 'date',
    'Produktionsindex Industrie (at; 2021=100)': 'econ_prod_index_industry',
    'Verbraucherpreisindex (2015=100)': 'econ_consumer_price_index',
    'Ausfuhren Insgesamt in €': 'econ_exports_total_EUR',
    'Umsatzindex Handel (nom.; 2021=100)': 'econ_turnover_index_commercial_sales',
    'Nächtigungen': 'econ_count_overnight_stays',
    'Umsatz Industrie inTsd.€ (KJE)': 'econ_turnover_industry',
    'Beschäftigte Industrie gesamt (KJE)': 'econ_count_employees_industry',
    'Produktionsindex Bau (at; 2021=100)': 'econ_prod_index_construction',
    'Technische Gesamtproduktion Bau in Tsd. € (KJE)': 'econ_total_production_construction',
    'Umsatzindex Bau (2021=100)': 'econ_turnover_index_construction',
    'Umsatz Bau in Tsd. € (KJE)': 'econ_turnover_construction',
    'Beschäftigte Bau gesamt (KJE)': 'econ_count_employees_construction',
    'Umsatzindex - Großhandel (G46; nom.; 2021=100)': 'econ_turnover_index_wholesale',
    'Umsatzindex - Einzelhandel (G47; nom.; 2021=100)': 'econ_turnover_index_retail',
    'Beschäftigtenindex Handel  (2021=100)': 'econ_count_employees_retail',
    'Umsatzindex - KfZ-Handel (G45; nom.; 2021=100)': 'econ_turnover_index_car_retail',
    'Einfuhren Insgesamt in €': 'econ_imports_total_EUR',
    'Einfuhren Insg. SITC-3 Brennstoffe, Energie in €': 'econ_imports_energy_EUR'
}

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def standardize_missing_values(df, additional_missing=None, show_quality_control=True):
    """Convert various missing value representations to pandas NaN."""
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

def is_valid_date_format(value):
    """Check if value matches Austrian economic date format mmm.yy"""
    if pd.isna(value) or value == '':
        return False
    try:
        s = str(value).strip()
        if '.' not in s:
            return False
        parts = s.split('.')
        return len(parts) == 2 and len(parts[0]) <= 4 and len(parts[1]) == 2
    except:
        return False

def parse_austrian_economic_date(date_str):
    """Parse Austrian date format mmm.yy to datetime. Example: 'Jän.09' → 2009-01-01"""
    if pd.isna(date_str):
        return pd.NaT
    
    try:
        month_abbr, year = str(date_str).strip().split('.')
        month_num = GERMAN_MONTHS.get(month_abbr, month_abbr)
        return pd.to_datetime(f"20{year}-{month_num}-01")
    except Exception as e:
        return pd.NaT

# =============================================================================
# DATA LOADING
# =============================================================================

def load_economy_data(file_path, skiprows, column_mapping):
    """
    Load economic indicators data from Excel and select relevant columns.
    Automatically detects end of data by validating date format.
    """
    try:
        # Load Excel file without nrows - will filter later
        df = pd.read_excel(file_path, skiprows=skiprows)
        
        print(f"INITIAL DATA LOAD:")
        print(f"  Original shape: {df.shape}")
        print()
        
        # Drop first column (empty index column)
        df = df.iloc[:, 1:]
        
        # Strip whitespace from column names
        df.columns = df.columns.str.strip()
        
        # Filter to valid data rows (only rows with valid date format)
        first_col = df.columns[0]
        valid_rows = df[first_col].apply(is_valid_date_format)
        rows_before = len(df)
        df = df[valid_rows].reset_index(drop=True)
        
        print(f"DATA ROW FILTERING:")
        print(f"  Rows before: {rows_before}, after: {len(df)}")
        print(f"  Removed {rows_before - len(df)} footer/invalid rows")
        print()
        
        # Parse Austrian dates
        df[first_col] = df[first_col].apply(parse_austrian_economic_date)
        
        print(f"DATE PARSING:")
        print(f"  Date range: {df[first_col].min()} to {df[first_col].max()}")
        print()
        
        # Clean missing values BEFORE renaming
        df_clean, missing_patterns = standardize_missing_values(df, show_quality_control=True)
        
        # Adjust column mapping to use actual first column name
        adjusted_mapping = column_mapping.copy()
        if first_col != 'Berichtszeitraum':
            adjusted_mapping[first_col] = adjusted_mapping.pop('Berichtszeitraum')
        
        # Rename columns to standardized names
        df_clean.rename(columns=adjusted_mapping, inplace=True)
        
        print(f"\nCOLUMN RENAMING:")
        print(f"  Renamed {len(adjusted_mapping)} columns with econ_ prefix")
        print()
        
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
        print(f"ERROR loading economic data: {e}")
        return None, {'error': str(e)}

# =============================================================================
# DATA TRANSFORMATION
# =============================================================================

def convert_economy_data_types(df):
    """Convert economic indicator columns to appropriate numeric types."""
    df_converted = df.copy()
    
    print("DATA TYPE CONVERSION:")
    print("-" * 40)
    
    econ_columns = [col for col in df_converted.columns if col.startswith('econ_')]
    
    print(f"Converting {len(econ_columns)} economic indicator columns to numeric")
    
    for col in econ_columns:
        df_converted[col] = pd.to_numeric(df_converted[col], errors='coerce')
        df_converted[col] = df_converted[col].astype('float64')
    
    print(f"  All columns converted to float64")
    print()
    
    return df_converted

def transform_economy_to_long_format(df, date_column='date'):
    """Transform economic data to long format (monthly only)."""
    print("\nTRANSFORMING TO LONG FORMAT:")
    print("-" * 40)
    print("ARCHITECTURAL NOTE: Creating MONTHLY rows only")
    print()
    
    df_long = df.copy()
    
    df_long[date_column] = pd.to_datetime(df_long[date_column])
    
    df_long['year'] = df_long[date_column].dt.year
    df_long['month'] = df_long[date_column].dt.month
    df_long['quarter'] = df_long[date_column].dt.quarter
    df_long['week'] = df_long[date_column].dt.isocalendar().week
    df_long['month_name'] = df_long[date_column].dt.month_name()
    df_long['aggregation_level'] = 'monthly'
    
    df_long['date'] = df_long[date_column].apply(lambda x: x.replace(day=1).strftime('%Y-%m-%d'))
    
    base_columns = ['date', 'year', 'month', 'quarter', 'week', 'aggregation_level', 'month_name']
    econ_columns = [col for col in df_long.columns if col.startswith('econ_')]
    final_columns = base_columns + econ_columns
    
    df_final = df_long[final_columns].copy()
    
    print(f"FINAL STRUCTURE:")
    print(f"  Rows: {len(df_final)} (monthly only)")
    print(f"  Columns: {len(df_final.columns)}")
    print(f"  Economic variables: {len(econ_columns)}")
    print(f"  Date range: {df_final['date'].min()} to {df_final['date'].max()}")
    print()
    
    return df_final

# =============================================================================
# DATA PERSISTENCE
# =============================================================================

def save_economy_dataset(df, output_dir, filename="economy_consolidated.csv"):
    """Save economic indicators dataset as separate validation sample."""
    if df is None or len(df) == 0:
        print("No economy data to save!")
        return None
    
    output_path = output_dir / filename
    df.to_csv(output_path, index=False, na_rep='')
    
    print(f"ECONOMIC INDICATORS DATASET SAVED:")
    print(f"  Path: {output_path}")
    print(f"  Rows: {len(df)}")
    print(f"  Columns: {len(df.columns)}")
    print(f"  Date range: {df['date'].min()} to {df['date'].max()}")
    
    econ_columns = [col for col in df.columns if col.startswith('econ_')]
    print(f"  Economic variables: {len(econ_columns)}")
    
    return output_path

def merge_economy_with_consolidated_data(economy_df, consolidated_file_path, output_dir):
    """Merge economic indicators data with existing consolidated data."""
    consolidated_path = Path(consolidated_file_path)
    
    if not consolidated_path.exists():
        print(f"ERROR: Consolidated file not found at {consolidated_path}")
        return pd.DataFrame()
    
    print("MERGING ECONOMIC INDICATORS WITH CONSOLIDATED DATA:")
    print("-" * 50)
    
    try:
        consolidated_df = pd.read_csv(consolidated_path)
        
        print(f"Existing consolidated data loaded:")
        print(f"  Shape: {consolidated_df.shape}")
        print()
        
        print(f"Economic data to merge:")
        print(f"  Shape: {economy_df.shape}")
        print(f"  Date range: {economy_df['date'].min()} to {economy_df['date'].max()}")
        print()
        
        merged_df = pd.merge(
            consolidated_df, 
            economy_df, 
            on=['date', 'aggregation_level'], 
            how='outer',
            suffixes=('', '_economy')
        )
        
        print(f"After merge: {merged_df.shape}")
        print()
        
        duplicate_cols = ['year', 'month', 'quarter', 'week', 'month_name']
        for col in duplicate_cols:
            economy_col = f"{col}_economy"
            if economy_col in merged_df.columns:
                merged_df[col] = merged_df[col].fillna(merged_df[economy_col])
                merged_df.drop(economy_col, axis=1, inplace=True)
                print(f"  Resolved duplicate: {col}")
        
        merged_df = merged_df.sort_values(['date', 'aggregation_level']).reset_index(drop=True)
        
        final_path = output_dir / "data_consolidated.csv"
        merged_df.to_csv(final_path, index=False, na_rep='')
        
        print(f"\nFINAL CONSOLIDATED DATASET:")
        print(f"  Saved to: {final_path}")
        print(f"  Final shape: {merged_df.shape}")
        print(f"  Date range: {merged_df['date'].min()} to {merged_df['date'].max()}")
        print()
        
        economy_columns = [col for col in merged_df.columns if col.startswith('econ_')]
        print(f"Economic indicator columns added ({len(economy_columns)}):")
        for col in economy_columns:
            non_null = merged_df[col].notna().sum()
            print(f"  {col}: {non_null} non-null values")
        
        return merged_df
        
    except Exception as e:
        print(f"ERROR during merge: {e}")
        return pd.DataFrame()

# =============================================================================
# MAIN PIPELINE
# =============================================================================

def consolidate_economy_data(raw_file, consolidated_file, output_dir):
    """Main pipeline to consolidate economic indicators data."""
    print("="*70)
    print("ECONOMIC INDICATORS DATA CONSOLIDATION PIPELINE")
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
    economy_df, metadata = load_economy_data(raw_file, SKIPROWS, COLUMN_MAPPING)
    
    if economy_df is None:
        print(f"Pipeline failed: {metadata.get('error', 'Unknown error')}")
        return pd.DataFrame()
    
    # Step 2: Convert data types
    print("\nSTEP 2: CONVERT DATA TYPES")
    print("-" * 70)
    economy_converted = convert_economy_data_types(economy_df)
    
    # Step 3: Transform to long format
    print("\nSTEP 3: TRANSFORM TO LONG FORMAT")
    print("-" * 70)
    economy_long = transform_economy_to_long_format(economy_converted)
    
    # Step 4: Save standalone file
    print("\nSTEP 4: SAVE STANDALONE FILE")
    print("-" * 70)
    save_economy_dataset(economy_long, output_dir)
    
    # Step 5: Merge with consolidated data
    print("\nSTEP 5: MERGE WITH CONSOLIDATED DATA")
    print("-" * 70)
    final_df = merge_economy_with_consolidated_data(economy_long, consolidated_file, output_dir)
    
    print("\n" + "="*70)
    print("PIPELINE COMPLETE")
    print("="*70)
    print(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if len(final_df) > 0:
        print("✓ Economic indicators data successfully integrated")
        print(f"✓ Final dataset: {final_df.shape[0]} rows × {final_df.shape[1]} columns")
    else:
        print("✗ Pipeline failed - check errors above")
    
    return final_df

# =============================================================================
# SCRIPT ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    raw_file = Path("data/raw/economy/table_2025-09-16_13-30-40.xlsx")
    consolidated_file = Path("data/processed/data_consolidated.csv")
    output_dir = Path("data/processed")
    
    final_df = consolidate_economy_data(raw_file, consolidated_file, output_dir)