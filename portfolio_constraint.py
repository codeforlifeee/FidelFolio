"""
Portfolio Constraint Application
Assignment FF26A1

Description:
This script applies portfolio-level constraints to investment strategies:
1. MCap Filter: Removes stocks in the bottom 20% by market capitalization
2. Sector Constraint: Limits each sector to maximum 25% of portfolio

Input Files:
- assignment_investment_rules.csv: Investment strategies with stock lists
- assignment_sector_data.csv: Company sector classifications
- assignment_mcap.csv: Market capitalization data by year

Output:
- output.csv: Modified investment rules with constraints applied
"""

import pandas as pd
import ast
from typing import List, Dict, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class PortfolioConstraintApplicator:
    """
    Applies portfolio-level constraints to investment strategies.
    
    Constraints:
    1. Market Cap Filter: Removes bottom 20% of stocks by market cap
    2. Sector Constraint: Limits each sector to 25% of portfolio
    """
    
    def __init__(self, rules_file: str, sector_file: str, mcap_file: str):
        """
        Initialize the constraint applicator with input data files.
        
        Args:
            rules_file: Path to investment rules CSV
            sector_file: Path to sector data CSV
            mcap_file: Path to market cap CSV
        """
        logger.info("Loading input data files...")
        
        # Load data
        self.investment_rules = pd.read_csv(rules_file)
        self.sector_data = pd.read_csv(sector_file)
        self.mcap_data = pd.read_csv(mcap_file)
        
        # Detect column names (handle variations)
        self.company_col = 'CO_NAME' if 'CO_NAME' in self.sector_data.columns else 'Company'
        self.sector_col = '[Sector' if '[Sector' in self.sector_data.columns else 'Sector'
        
        # Build lookup dictionaries for efficient access
        self._build_sector_dict()
        self._build_mcap_dict()
        
        logger.info(f"Loaded {len(self.investment_rules)} investment strategies")
        logger.info(f"Loaded {len(self.sector_dict)} companies with sector data")
        logger.info(f"Loaded market cap data for {len(self.mcap_dict)} companies")
    
    def _build_sector_dict(self):
        """Build a dictionary mapping company names to sectors."""
        self.sector_dict = {}
        for _, row in self.sector_data.iterrows():
            company = row[self.company_col]
            sector = row[self.sector_col]
            self.sector_dict[company] = sector
    
    def _build_mcap_dict(self):
        """Build a nested dictionary: {company: {year: mcap}}."""
        self.mcap_dict = {}
        for _, row in self.mcap_data.iterrows():
            company = row[self.company_col]
            self.mcap_dict[company] = {}
            
            # Iterate through year columns
            for col in self.mcap_data.columns:
                if col != self.company_col and pd.notna(row[col]):
                    year = col
                    mcap_value = float(row[col])
                    self.mcap_dict[company][year] = mcap_value
    
    def parse_stock_list(self, stocks_str: str) -> List[str]:
        """
        Parse a stock list string into a Python list.
        
        Args:
            stocks_str: String representation of stock list
            
        Returns:
            List of stock symbols
        """
        if pd.isna(stocks_str) or str(stocks_str).strip() == '':
            return []
        
        try:
            # Try direct AST parsing first
            return ast.literal_eval(stocks_str)
        except:
            # Fallback: manual parsing
            stocks_str = str(stocks_str).strip()
            if stocks_str.startswith('[') and stocks_str.endswith(']'):
                stocks_str = stocks_str[1:-1]
            
            stocks = []
            for item in stocks_str.split(','):
                item = item.strip().strip("'\"")
                if item:
                    stocks.append(item)
            return stocks
    
    def apply_mcap_filter(self, stocks: List[str], year: str) -> Tuple[List[str], List[str]]:
        """
        Apply market cap filter: remove bottom 20% of stocks by MCap.
        
        Args:
            stocks: List of stock symbols
            year: Year column name for MCap lookup
            
        Returns:
            Tuple of (kept_stocks, excluded_stocks)
        """
        if not stocks:
            return [], []
        
        # Get MCap for each stock
        stocks_with_mcap = []
        for stock in stocks:
            mcap = self.mcap_dict.get(stock, {}).get(year, 0)
            stocks_with_mcap.append((stock, mcap))
        
        # Sort by MCap descending (highest first)
        stocks_with_mcap.sort(key=lambda x: x[1], reverse=True)
        
        # Calculate cutoff: keep top 80%, remove bottom 20%
        cutoff_index = int(len(stocks_with_mcap) * 0.8)
        
        kept = [stock for stock, _ in stocks_with_mcap[:cutoff_index]]
        excluded = [stock for stock, _ in stocks_with_mcap[cutoff_index:]]
        
        return kept, excluded
    
    def apply_sector_constraint(self, stocks: List[str], year: str) -> Tuple[List[str], List[str]]:
        """
        Apply sector constraint: limit each sector to 25% of portfolio.
        
        For over-concentrated sectors, remove stocks with lowest MCap.
        
        Args:
            stocks: List of stock symbols
            year: Year column name for MCap lookup
            
        Returns:
            Tuple of (kept_stocks, excluded_stocks)
        """
        if not stocks:
            return [], []
        
        # Calculate maximum allowed per sector (25% of total)
        max_per_sector = int(len(stocks) * 0.25)
        
        # Group stocks by sector with their MCap
        stocks_by_sector = {}
        for stock in stocks:
            sector = self.sector_dict.get(stock, 'Unknown')
            if sector not in stocks_by_sector:
                stocks_by_sector[sector] = []
            
            mcap = self.mcap_dict.get(stock, {}).get(year, 0)
            stocks_by_sector[sector].append((stock, mcap))
        
        # For each sector, sort by MCap and keep only top stocks up to limit
        kept = []
        excluded = []
        
        for sector, sector_stocks in stocks_by_sector.items():
            # Sort by MCap descending
            sector_stocks.sort(key=lambda x: x[1], reverse=True)
            
            # Keep up to max_per_sector stocks
            for i, (stock, mcap) in enumerate(sector_stocks):
                if i < max_per_sector:
                    kept.append(stock)
                else:
                    excluded.append(stock)
        
        return kept, excluded
    
    def process_all_strategies(self) -> pd.DataFrame:
        """
        Process all investment strategies and apply constraints.
        
        Returns:
            DataFrame with constrained portfolios
        """
        logger.info("\nApplying constraints to all strategies...")
        
        # Create output dataframe
        output_df = self.investment_rules.copy()
        
        # Get year columns (all except strategy name)
        year_columns = [col for col in self.investment_rules.columns if col != 'strat_name']
        
        total_strategies = len(output_df)
        total_excluded_mcap = 0
        total_excluded_sector = 0
        
        # Process each strategy
        for idx, row in output_df.iterrows():
            if (idx + 1) % 10 == 0:
                logger.info(f"Processing strategy {idx + 1}/{total_strategies}...")
            
            for year_col in year_columns:
                stocks_str = row[year_col]
                
                if pd.isna(stocks_str) or str(stocks_str).strip() == '':
                    continue
                
                try:
                    # Parse stock list
                    stocks = self.parse_stock_list(stocks_str)
                    
                    if not stocks:
                        continue
                    
                    original_count = len(stocks)
                    
                    # Apply MCap filter
                    stocks, mcap_excluded = self.apply_mcap_filter(stocks, year_col)
                    total_excluded_mcap += len(mcap_excluded)
                    
                    # Apply sector constraint
                    stocks, sector_excluded = self.apply_sector_constraint(stocks, year_col)
                    total_excluded_sector += len(sector_excluded)
                    
                    # Update the dataframe with constrained portfolio
                    output_df.at[idx, year_col] = str(stocks)
                    
                except Exception as e:
                    logger.warning(f"Error processing strategy {idx+1}, year {year_col}: {str(e)}")
                    continue
        
        logger.info("\nConstraint application complete!")
        logger.info(f"Total stocks excluded by MCap filter: {total_excluded_mcap}")
        logger.info(f"Total stocks excluded by sector constraint: {total_excluded_sector}")
        logger.info(f"Total combined exclusions: {total_excluded_mcap + total_excluded_sector}")
        
        return output_df
    
    def save_output(self, output_df: pd.DataFrame, output_file: str = 'output.csv'):
        """
        Save the constrained portfolios to CSV file.
        
        Args:
            output_df: DataFrame with constrained portfolios
            output_file: Output file path
        """
        output_df.to_csv(output_file, index=False)
        logger.info(f"\n Output saved to: {output_file}")
        
        # Print file size
        import os
        file_size_mb = os.path.getsize(output_file) / (1024 * 1024)
        logger.info(f"File size: {file_size_mb:.2f} MB")


def main():
    """Main execution function."""
    
    print("=" * 70)
    print("PORTFOLIO CONSTRAINT APPLICATION - Assignment FF26A1")
    print("=" * 70)
    
    # Input files
    rules_file = 'assignment_investment_rules.csv'
    sector_file = 'assignment_sector_data.csv'
    mcap_file = 'assignment_mcap.csv'
    
    # Initialize constraint applicator
    applicator = PortfolioConstraintApplicator(rules_file, sector_file, mcap_file)
    
    # Process all strategies
    output_df = applicator.process_all_strategies()
    
    # Save output
    applicator.save_output(output_df, 'output.csv')
    
    print("\n" + "=" * 70)
    print("PORTFOLIO CONSTRAINT APPLICATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
