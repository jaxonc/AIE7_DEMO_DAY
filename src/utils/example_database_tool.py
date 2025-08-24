from langchain.tools import BaseTool
from typing import Optional
import pandas as pd
import os
import sys

class ExampleDatabaseTool(BaseTool):
    name: str = "example_database_lookup"
    description: str = "Searches the example SQL database for product information using a valid UPC code. If found, returns product name and description without searching other databases. Input should be a valid UPC code as a string."
    
    def __init__(self):
        super().__init__()
        # Hardcode the database path
        self._database_path = '/Users/Work/Desktop/ai_bootcamp/code/Cert_Challenge/AIE7_DEMO_DAY/example_database/example_sql_database.csv'
        self._database = self._load_database()
    
    def _load_database(self) -> pd.DataFrame:
        """
        Load the example database CSV file into a pandas DataFrame.
        
        Returns:
            pd.DataFrame: Loaded database
        """
        try:
            if not os.path.exists(self._database_path):
                raise FileNotFoundError(f"Database file not found at: {self._database_path}")
            
            df = pd.read_csv(self._database_path)
            # Clean the UPC column - remove any leading zeros and ensure it's string
            df['UPC'] = df['UPC'].astype(str).str.zfill(12)
            return df
        except Exception as e:
            raise Exception(f"Failed to load example database: {str(e)}")
    
    def _run(self, upc: str) -> str:
        """
        Search for product information in the example database.
        
        Args:
            upc (str): Valid UPC code
            
        Returns:
            str: Product information from example database or indication that product was not found
        """
        try:
            # Clean the input UPC - remove leading zeros and ensure it's 12 digits
            clean_upc = str(upc).zfill(12)
            
            # Search for the UPC in the database
            match = self._database[self._database['UPC'] == clean_upc]
            
            if not match.empty:
                product = match.iloc[0]
                
                result = {
                    "found": True,
                    "upc": clean_upc,
                    "product_name": product.get('PRODUCT_NAME', 'N/A'),
                    "description": product.get('DESCRIPTION', 'N/A')
                }
                
                return f"""Product found in Example Database:

UPC: {result['upc']}
Product Name: {result['product_name']}
Description: {result['description']}

This information is sourced directly from the example database. No additional database or web searches are needed for this product."""
            
            else:
                return f"Product with UPC {upc} was not found in the example database. The UPC may be valid but the product is not in this database."
                
        except Exception as e:
            return f"Error searching example database for UPC {upc}: {str(e)}"
    
    def _arun(self, upc: str) -> str:
        """
        Async version of the run method.
        
        Args:
            upc (str): Valid UPC code
            
        Returns:
            str: Product information from example database
        """
        # For now, just call the synchronous version
        return self._run(upc)
