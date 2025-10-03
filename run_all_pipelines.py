"""
Master Pipeline Script
Runs all 6 data ingestion pipelines in sequence

Usage: python run_all_pipelines.py
"""

import sys
from pathlib import Path
from datetime import datetime

# Import all pipeline modules
sys.path.append(str(Path(__file__).parent))

try:
    from importlib import import_module
    
    # Pipeline modules in order
    PIPELINES = [
        '01_electricity_data_ingestion',
        '02_carbon_data_ingestion',
        '03_climate_data_ingestion',
        '04_production_mix_data_ingestion',
        '05_gas_prices_data_ingestion',
        '06_economic_data_ingestion'
    ]
    
    def run_all_pipelines():
        """Execute all data ingestion pipelines in sequence."""
        print("="*80)
        print("MASTER PIPELINE EXECUTION")
        print("="*80)
        print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Pipelines to execute: {len(PIPELINES)}")
        print("="*80)
        print()
        
        results = {}
        
        for i, pipeline_name in enumerate(PIPELINES, 1):
            print(f"\n{'='*80}")
            print(f"EXECUTING PIPELINE {i}/{len(PIPELINES)}: {pipeline_name}")
            print(f"{'='*80}\n")
            
            try:
                # Import and run pipeline
                pipeline = import_module(pipeline_name)
                
                # Each pipeline has a consolidate_X_data() function
                if hasattr(pipeline, 'consolidate_electricity_data'):
                    raw_file = Path("data/raw/day_ahead_prices")
                    output_file = Path("data/processed/electricity_consolidated.csv")
                    result = pipeline.consolidate_electricity_data(raw_file, output_file)
                    
                elif hasattr(pipeline, 'consolidate_carbon_data'):
                    raw_file = Path("data/raw/carbon_prices/icap-graph-price-data-2015-01-01-2025-09-12.csv")
                    electricity_file = Path("data/processed/electricity_consolidated.csv")
                    output_dir = Path("data/processed")
                    result = pipeline.consolidate_carbon_data(raw_file, electricity_file, output_dir)
                    
                elif hasattr(pipeline, 'consolidate_climate_data'):
                    raw_file = Path("data/raw/climate/nrg_chddr2_m__custom_17979334_linear_2_0.csv")
                    consolidated_file = Path("data/processed/data_consolidated.csv")
                    output_dir = Path("data/processed")
                    result = pipeline.consolidate_climate_data(raw_file, consolidated_file, output_dir)
                    
                elif hasattr(pipeline, 'consolidate_production_data'):
                    raw_file = Path("data/raw/production_mix/el_dataset_mn.csv")
                    consolidated_file = Path("data/processed/data_consolidated.csv")
                    output_dir = Path("data/processed")
                    result = pipeline.consolidate_production_data(raw_file, consolidated_file, output_dir)
                    
                elif hasattr(pipeline, 'consolidate_gas_data'):
                    raw_file = Path("data/raw/gas_prices/oegpi_data.xlsx")
                    consolidated_file = Path("data/processed/data_consolidated.csv")
                    output_dir = Path("data/processed")
                    result = pipeline.consolidate_gas_data(raw_file, consolidated_file, output_dir)
                    
                elif hasattr(pipeline, 'consolidate_economy_data'):
                    raw_file = Path("data/raw/economy/table_2025-09-16_13-30-40.xlsx")
                    consolidated_file = Path("data/processed/data_consolidated.csv")
                    output_dir = Path("data/processed")
                    result = pipeline.consolidate_economy_data(raw_file, consolidated_file, output_dir)
                
                # Check if pipeline succeeded
                if result is not None and len(result) > 0:
                    results[pipeline_name] = {
                        'status': 'SUCCESS',
                        'rows': len(result),
                        'columns': len(result.columns)
                    }
                    print(f"\n✓ {pipeline_name} completed successfully")
                else:
                    results[pipeline_name] = {'status': 'FAILED'}
                    print(f"\n✗ {pipeline_name} failed")
                    
            except Exception as e:
                results[pipeline_name] = {
                    'status': 'ERROR',
                    'error': str(e)
                }
                print(f"\n✗ {pipeline_name} encountered error: {e}")
                # Continue with next pipeline instead of stopping
        
        # Final summary
        print("\n" + "="*80)
        print("MASTER PIPELINE SUMMARY")
        print("="*80)
        print(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        successful = sum(1 for r in results.values() if r['status'] == 'SUCCESS')
        failed = len(results) - successful
        
        print(f"Results: {successful}/{len(PIPELINES)} pipelines successful")
        print()
        
        for pipeline, result in results.items():
            status_symbol = "✓" if result['status'] == 'SUCCESS' else "✗"
            print(f"  {status_symbol} {pipeline}: {result['status']}")
            if result['status'] == 'SUCCESS':
                print(f"      Final shape: {result['rows']} rows × {result['columns']} columns")
            elif result['status'] == 'ERROR':
                print(f"      Error: {result.get('error', 'Unknown')}")
        
        print("\n" + "="*80)
        
        if failed == 0:
            print("✓ ALL PIPELINES COMPLETED SUCCESSFULLY")
            print("✓ data_consolidated.csv contains all 6 datasets")
        else:
            print(f"⚠ {failed} pipeline(s) failed - check errors above")
        
        print("="*80)
        
        return results
    
    if __name__ == "__main__":
        results = run_all_pipelines()
        
        # Exit with error code if any pipeline failed
        failed = sum(1 for r in results.values() if r['status'] != 'SUCCESS')
        sys.exit(1 if failed > 0 else 0)
        
except ImportError as e:
    print(f"ERROR: Could not import pipeline modules: {e}")
    print("Make sure all pipeline scripts (01_*.py through 06_*.py) are in the same directory")
    sys.exit(1)