"""
Consolidated Data Diagnostics Script
Runs comprehensive quality control diagnostics on data_consolidated.csv

Usage: python diagnostics.py
"""

import pandas as pd
from pathlib import Path
from datetime import datetime

def run_comprehensive_diagnostics(consolidated_file_path):
    """
    Run comprehensive quality control diagnostics on final consolidated dataset.
    Verifies data integrity, completeness, and structure across all data sources.
    
    Args:
        consolidated_file_path (Path): Path to data_consolidated.csv
    
    Returns:
        DataFrame: Loaded consolidated dataset for further inspection
    """
    consolidated_path = Path(consolidated_file_path)
    
    if not consolidated_path.exists():
        print(f"ERROR: Consolidated file not found at {consolidated_path}")
        return None
    
    # Capture start time
    start_time = datetime.now()
    
    print("="*70)
    print("COMPREHENSIVE DIAGNOSTICS: data_consolidated.csv")
    print("="*70)
    print()
    
    try:
        df = pd.read_csv(consolidated_path)
        
        # =====================================================================
        # 1. OVERALL STRUCTURE
        # =====================================================================
        print("1. OVERALL STRUCTURE:")
        print("-" * 70)
        print(f"  Shape: {df.shape[0]} rows × {df.shape[1]} columns")
        print(f"  Date range (overall): {df['date'].min()} to {df['date'].max()}")
        print(f"  Memory usage: {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")
        print()
        
        # =====================================================================
        # 2. AGGREGATION LEVEL DISTRIBUTION
        # =====================================================================
        print("2. AGGREGATION LEVEL DISTRIBUTION:")
        print("-" * 70)
        agg_counts = df['aggregation_level'].value_counts().sort_index()
        for level, count in agg_counts.items():
            pct = (count / len(df)) * 100
            date_range_level = df[df['aggregation_level'] == level]['date'].agg(['min', 'max'])
            print(f"  {level:10s}: {count:5d} rows ({pct:5.1f}%) | Range: {date_range_level['min']} to {date_range_level['max']}")
        print()
        
        # =====================================================================
        # 3. COLUMN INVENTORY BY DATA SOURCE
        # =====================================================================
        print("3. COLUMN INVENTORY BY DATA SOURCE:")
        print("-" * 70)
        
        base_cols = ['date', 'year', 'month', 'quarter', 'week', 'aggregation_level', 'month_name']
        electricity_cols = [col for col in df.columns if col.startswith('price_') or col == 'data_completeness']
        carbon_cols = [col for col in df.columns if col.startswith('carbonprices_')]
        climate_cols = [col for col in df.columns if col.startswith('climate_')]
        production_cols = [col for col in df.columns if col.startswith('prod_')]
        gas_cols = [col for col in df.columns if col.startswith('oegpi_')]
        economy_cols = [col for col in df.columns if col.startswith('econ_')]
        
        print(f"  Base structure: {len(base_cols)} columns")
        print(f"  Electricity:    {len(electricity_cols)} columns - {electricity_cols}")
        print(f"  Carbon:         {len(carbon_cols)} columns - {carbon_cols}")
        print(f"  Climate:        {len(climate_cols)} columns - {climate_cols}")
        print(f"  Production:     {len(production_cols)} columns")
        if len(production_cols) > 0:
            print(f"    (Showing first 5: {production_cols[:5]})")
        print(f"  Gas Prices:     {len(gas_cols)} columns - {gas_cols}")
        print(f"  Economy:        {len(economy_cols)} columns")
        if len(economy_cols) > 0:
            print(f"    (Showing first 5: {economy_cols[:5]})")
        print(f"  Total: {len(df.columns)} columns")
        print()
        
        # =====================================================================
        # 4. MISSING VALUES ANALYSIS
        # =====================================================================
        print("4. MISSING VALUES ANALYSIS:")
        print("-" * 70)
        
        def analyze_missing_by_source(columns, source_name):
            if len(columns) == 0:
                print(f"  {source_name}: No columns found")
                return
            
            print(f"  {source_name}:")
            for col in columns:
                missing_count = df[col].isna().sum()
                missing_pct = (missing_count / len(df)) * 100
                print(f"    {col:45s}: {missing_count:5d} missing ({missing_pct:5.1f}%)")
        
        analyze_missing_by_source(electricity_cols, "ELECTRICITY")
        print()
        analyze_missing_by_source(carbon_cols, "CARBON")
        print()
        analyze_missing_by_source(climate_cols, "CLIMATE")
        print()
        
        # Production columns - show all
        if len(production_cols) > 0:
            print(f"  PRODUCTION (summary of {len(production_cols)} columns):")
            for col in production_cols:
                missing_count = df[col].isna().sum()
                missing_pct = (missing_count / len(df)) * 100
                print(f"    {col:45s}: {missing_count:5d} missing ({missing_pct:5.1f}%)")
        print()
        
        analyze_missing_by_source(gas_cols, "GAS PRICES")
        print()
        
        # Economy columns - show all
        if len(economy_cols) > 0:
            print(f"  ECONOMY (summary of {len(economy_cols)} columns):")
            for col in economy_cols:
                missing_count = df[col].isna().sum()
                missing_pct = (missing_count / len(df)) * 100
                print(f"    {col:45s}: {missing_count:5d} missing ({missing_pct:5.1f}%)")
        print()
        
        # =====================================================================
        # 5. DATA TYPES VERIFICATION
        # =====================================================================
        print("5. DATA TYPES VERIFICATION:")
        print("-" * 70)
        print("  Expected: All numeric columns should be float64 (due to CSV format)")
        print()
        
        numeric_cols = electricity_cols + carbon_cols + climate_cols + production_cols + gas_cols + economy_cols
        non_float_cols = [col for col in numeric_cols if df[col].dtype != 'float64']
        
        if len(non_float_cols) > 0:
            print(f"  WARNING: {len(non_float_cols)} columns are not float64:")
            for col in non_float_cols:
                print(f"    {col}: {df[col].dtype}")
        else:
            print(f"  ✓ All {len(numeric_cols)} numeric columns are float64")
        print()
        
        # =====================================================================
        # 6. ARCHITECTURAL VALIDATION
        # =====================================================================
        print("6. ARCHITECTURAL VALIDATION:")
        print("-" * 70)
        
        # Check daily rows - should only have electricity + carbon
        daily_df = df[df['aggregation_level'] == 'daily']
        if len(daily_df) > 0:
            daily_climate_nulls = daily_df[climate_cols].isna().all(axis=1).sum()
            daily_prod_nulls = daily_df[production_cols].isna().all(axis=1).sum() if len(production_cols) > 0 else len(daily_df)
            daily_gas_nulls = daily_df[gas_cols].isna().all(axis=1).sum() if len(gas_cols) > 0 else len(daily_df)
            daily_econ_nulls = daily_df[economy_cols].isna().all(axis=1).sum() if len(economy_cols) > 0 else len(daily_df)
            print(f"  Daily rows ({len(daily_df)}):")
            print(f"    Climate columns all null: {daily_climate_nulls}/{len(daily_df)} rows ({daily_climate_nulls/len(daily_df)*100:.1f}%) ✓")
            print(f"    Production columns all null: {daily_prod_nulls}/{len(daily_df)} rows ({daily_prod_nulls/len(daily_df)*100:.1f}%) ✓")
            print(f"    Gas columns all null: {daily_gas_nulls}/{len(daily_df)} rows ({daily_gas_nulls/len(daily_df)*100:.1f}%) ✓")
            print(f"    Economy columns all null: {daily_econ_nulls}/{len(daily_df)} rows ({daily_econ_nulls/len(daily_df)*100:.1f}%) ✓")
        
        # Check weekly rows - should only have electricity + carbon
        weekly_df = df[df['aggregation_level'] == 'weekly']
        if len(weekly_df) > 0:
            weekly_climate_nulls = weekly_df[climate_cols].isna().all(axis=1).sum()
            weekly_prod_nulls = weekly_df[production_cols].isna().all(axis=1).sum() if len(production_cols) > 0 else len(weekly_df)
            weekly_gas_nulls = weekly_df[gas_cols].isna().all(axis=1).sum() if len(gas_cols) > 0 else len(weekly_df)
            weekly_econ_nulls = weekly_df[economy_cols].isna().all(axis=1).sum() if len(economy_cols) > 0 else len(weekly_df)
            print(f"  Weekly rows ({len(weekly_df)}):")
            print(f"    Climate columns all null: {weekly_climate_nulls}/{len(weekly_df)} rows ({weekly_climate_nulls/len(weekly_df)*100:.1f}%) ✓")
            print(f"    Production columns all null: {weekly_prod_nulls}/{len(weekly_df)} rows ({weekly_prod_nulls/len(weekly_df)*100:.1f}%) ✓")
            print(f"    Gas columns all null: {weekly_gas_nulls}/{len(weekly_df)} rows ({weekly_gas_nulls/len(weekly_df)*100:.1f}%) ✓")
            print(f"    Economy columns all null: {weekly_econ_nulls}/{len(weekly_df)} rows ({weekly_econ_nulls/len(weekly_df)*100:.1f}%) ✓")
        
        # Check monthly rows - should have all sources
        monthly_df = df[df['aggregation_level'] == 'monthly']
        if len(monthly_df) > 0:
            monthly_climate_data = monthly_df[climate_cols].notna().any(axis=1).sum()
            monthly_prod_data = monthly_df[production_cols].notna().any(axis=1).sum() if len(production_cols) > 0 else 0
            monthly_gas_data = monthly_df[gas_cols].notna().any(axis=1).sum() if len(gas_cols) > 0 else 0
            monthly_econ_data = monthly_df[economy_cols].notna().any(axis=1).sum() if len(economy_cols) > 0 else 0
            print(f"  Monthly rows ({len(monthly_df)}):")
            print(f"    Rows with climate data: {monthly_climate_data}/{len(monthly_df)} ({monthly_climate_data/len(monthly_df)*100:.1f}%)")
            print(f"    Rows with production data: {monthly_prod_data}/{len(monthly_df)} ({monthly_prod_data/len(monthly_df)*100:.1f}%)")
            print(f"    Rows with gas data: {monthly_gas_data}/{len(monthly_df)} ({monthly_gas_data/len(monthly_df)*100:.1f}%)")
            print(f"    Rows with economy data: {monthly_econ_data}/{len(monthly_df)} ({monthly_econ_data/len(monthly_df)*100:.1f}%)")
        print()
        
        # =====================================================================
        # 7. SAMPLE DATA FROM EACH AGGREGATION LEVEL
        # =====================================================================
        print("7. SAMPLE DATA FROM EACH AGGREGATION LEVEL:")
        print("-" * 70)
        
        for level in ['daily', 'weekly', 'monthly']:
            level_df = df[df['aggregation_level'] == level]
            if len(level_df) > 0:
                print(f"\n  {level.upper()} sample (first 3 rows):")
                # Show subset of columns for readability
                sample_cols = ['date', 'aggregation_level', 'price_exaa_mean', 'carbonprices_primary_market']
                if level == 'monthly':
                    sample_cols.extend(['climate_hdd_at', 'prod_gross_electricity_production', 'oegpi_month'])
                    if len(economy_cols) > 0:
                        sample_cols.append(economy_cols[0])  # Add first economy column if exists
                display_cols = [col for col in sample_cols if col in level_df.columns]
                print(level_df[display_cols].head(3).to_string(index=False))
        
        print()
        print("="*70)
        print("DIAGNOSTICS COMPLETE")
        print("="*70)
        
        # Capture end time and display timestamp
        end_time = datetime.now()
        timestamp = end_time.strftime('%Y-%m-%d-%H-%M-%S')
        duration = (end_time - start_time).total_seconds()
        
        print(f"\nDiagnostics completed at: {timestamp}")
        print(f"Execution time: {duration:.2f} seconds")
        
        return df
        
    except Exception as e:
        print(f"ERROR during diagnostics: {e}")
        import traceback
        traceback.print_exc()
        return None

# =============================================================================
# SCRIPT ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    # Setup path
    consolidated_file = Path("data/processed/data_consolidated.csv")
    
    print("Starting diagnostics...")
    print(f"Target file: {consolidated_file}")
    print()
    
    # Run diagnostics
    final_df = run_comprehensive_diagnostics(consolidated_file)
    
    if final_df is not None:
        print("\n✓ data_consolidated.csv diagnostics complete")
        
        # Determine which datasets are included based on columns
        datasets = ["Electricity", "Carbon"]
        if any(col.startswith('climate_') for col in final_df.columns):
            datasets.append("Climate")
        if any(col.startswith('prod_') for col in final_df.columns):
            datasets.append("Production")
        if any(col.startswith('oegpi_') for col in final_df.columns):
            datasets.append("Gas")
        if any(col.startswith('econ_') for col in final_df.columns):
            datasets.append("Economy")
        
        print(f"  Contains: {' + '.join(datasets)}")
        print(f"  Total: {final_df.shape[0]} rows × {final_df.shape[1]} columns")
    else:
        print("\n✗ Diagnostics failed - check errors above")