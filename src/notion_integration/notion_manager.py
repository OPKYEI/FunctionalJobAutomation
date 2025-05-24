import os
from typing import Dict, Any, List
from notion_client import Client
import pandas as pd
from dotenv import load_dotenv
from src.config import NOTION_API_KEY, NOTION_SCHEMA, NOTION_DATABASE_ID

class NotionManager:
    def __init__(self, df, database_id: str = NOTION_DATABASE_ID):
        try:
            # Print debug info about database ID
            print(f"Using Notion database ID: {database_id}")
            # Don't modify the database ID format at all, use it exactly as is
            
            # Check if API key is loaded
            load_dotenv()  # Ensure env vars are loaded
            api_key = os.getenv("NOTION_API_KEY", NOTION_API_KEY)
            if not api_key:
                print("ERROR: No NOTION_API_KEY found in environment variables or config")
                print("Make sure your .env file contains a valid NOTION_API_KEY")
                return
            else:
                print("NOTION_API_KEY is loaded (not showing for security)")
                print(f"API key length: {len(api_key)} characters")
            
            # Initialize Notion client
            print("Initializing Notion client...")
            self.notion = self._initialize_notion_client()
            print("Notion client initialized successfully")
            
            # Set properties
            self.df = df
            self.database_id = database_id  # Store as-is, don't format
            
            # Print DataFrame info for debugging
            print(f"DataFrame received with {len(df)} rows and columns: {df.columns.tolist()}")
            
            # Check required columns
            required_columns = ["job_id", "job_position_title", "company_name"]
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                print(f"ERROR: Required columns missing from DataFrame: {missing_columns}")
                return
                
            if df.empty:
                print("WARNING: Empty DataFrame received, nothing to sync to Notion")
                return
                
            # Test database access before syncing
            try:
                print(f"Testing database access with ID: {database_id}")
                # Use database_id exactly as-is - no modification
                db_info = self.notion.databases.retrieve(database_id=database_id)
                print(f"Successfully connected to database titled: {db_info.get('title', [{}])[0].get('plain_text', 'Unnamed Database')}")
                print(f"Database has {len(db_info.get('properties', {}))} properties")
                
                # List database properties
                print("Database properties:")
                for prop_name, prop_details in db_info.get('properties', {}).items():
                    print(f"  - {prop_name} ({prop_details.get('type', 'unknown type')})")
                
            except Exception as e:
                print(f"ERROR accessing Notion database: {str(e)}")
                print("Please verify:")
                print("1. The database ID is correct")
                print("2. Your integration has been added to the database (Share button)")
                print("3. Your API key is valid and belongs to the correct workspace")
                return
            
            # Proceed with sync
            print("Proceeding with sync to Notion...")
            self.sync_to_notion(self.df)
            
        except Exception as e:
            print(f"ERROR initializing NotionManager: {str(e)}")
            import traceback
            traceback.print_exc()

    @staticmethod
    def _initialize_notion_client() -> Client:
        load_dotenv()
        api_key = os.getenv("NOTION_API_KEY", NOTION_API_KEY)
        if not api_key:
            raise ValueError("Notion API key not found in environment variables or config")
        return Client(auth=api_key)

    def create_property(self, property_name: str, property_type: str) -> None:
        try:
            self.notion.databases.update(
                database_id=self.database_id,  # Use as-is
                properties={
                    property_name: {
                        "type": property_type,
                        property_type: {}
                    }
                }
            )
            print(f"Property '{property_name}' of type '{property_type}' created successfully.")
        except Exception as e:
            print(f"Error creating property: {e}")

    def sync_to_notion(self, df: pd.DataFrame) -> None:
        if df.empty:
            print("Warning: DataFrame is empty. No data to sync to Notion.")
            return
            
        print(f"Starting Notion sync with {len(df)} rows...")
        print(f"Using database ID exactly as provided (not modified): {self.database_id}")
        
        # Print DataFrame columns for debugging
        print(f"DataFrame columns: {df.columns.tolist()}")
        
        success_count = 0
        error_count = 0
        
        for idx, row in df.iterrows():
            try:
                # Get job ID for logging
                job_id = row.get('job_id', 'Unknown')
                print(f"Processing row {idx}: Job ID: {job_id}")
                
                # Prepare properties
                properties = self._prepare_properties(row)
                
                # Check if we have any properties
                if not properties:
                    print(f"Warning: No valid properties for job ID {job_id}, skipping")
                    error_count += 1
                    continue
                    
                # Get company logo or use default
                company_logo = row.get('company_logo', "https://img.icons8.com/color/48/000000/company.png")
                if pd.isna(company_logo) or company_logo == "":
                    company_logo = "https://img.icons8.com/color/48/000000/company.png"
                
                # Create page in Notion - use database_id exactly as stored
                page_data = {
                    "parent": {"database_id": self.database_id},  # Use database_id as-is
                    "properties": properties
                }
                
                # Add icon if available
                if company_logo and company_logo != "":
                    page_data["icon"] = {"type": "external", "external": {"url": company_logo}}
                
                # Create the page
                page = self.notion.pages.create(**page_data)
                
                # Add detailed content if available
                if 'job_description' in row:
                    self.add_detailed_content(page["id"], row)
                
                print(f"Row added successfully: {job_id}")
                success_count += 1
                
            except Exception as e:
                print(f"Error adding row {idx}: {row.get('job_id', 'Unknown')}. Error: {str(e)}")
                error_count += 1
        
        print(f"Notion sync complete. Success: {success_count}, Errors: {error_count}")

    def _prepare_properties(self, row: pd.Series) -> Dict[str, Any]:
        properties = {}
        
        # Print available columns for debugging
        row_dict = row.to_dict()
        print(f"Row data keys: {list(row_dict.keys())}")
        
        for col, prop_data in NOTION_SCHEMA.items():
            notion_prop_name = prop_data["notion_prop_name"]
            notion_type = prop_data["type"]
            
            # Check if column exists
            if col not in row_dict:
                print(f"Warning: Column '{col}' not found in row. Using default value.")
                
                # Use appropriate defaults based on type
                if notion_type == "title":
                    properties[notion_prop_name] = {"title": [{"text": {"content": f"Unknown {notion_prop_name}"}}]}
                elif notion_type == "rich_text":
                    properties[notion_prop_name] = {"rich_text": [{"text": {"content": ""}}]}
                elif notion_type == "number":
                    properties[notion_prop_name] = {"number": None}
                elif notion_type == "select":
                    properties[notion_prop_name] = {"select": {"name": "Not specified"}}
                elif notion_type == "multi_select":
                    properties[notion_prop_name] = {"multi_select": []}
                elif notion_type == "date":
                    properties[notion_prop_name] = {"date": None}
                elif notion_type == "checkbox":
                    properties[notion_prop_name] = {"checkbox": False}
                elif notion_type == "url":
                    properties[notion_prop_name] = {"url": None}
                    
                continue
                
            # Get value safely
            value = row_dict.get(col)
            
            # Skip empty values as needed
            if pd.isna(value) or value == "":
                print(f"Warning: Empty value for '{col}'. Using default.")
                
                # Use appropriate defaults based on type
                if notion_type == "title":
                    properties[notion_prop_name] = {"title": [{"text": {"content": f"Unknown {notion_prop_name}"}}]}
                elif notion_type == "rich_text":
                    properties[notion_prop_name] = {"rich_text": [{"text": {"content": ""}}]}
                elif notion_type == "number":
                    properties[notion_prop_name] = {"number": None}
                elif notion_type == "select":
                    properties[notion_prop_name] = {"select": {"name": "Not specified"}}
                elif notion_type == "multi_select":
                    properties[notion_prop_name] = {"multi_select": []}
                elif notion_type == "date":
                    properties[notion_prop_name] = {"date": None}
                elif notion_type == "checkbox":
                    properties[notion_prop_name] = {"checkbox": False}
                elif notion_type == "url":
                    properties[notion_prop_name] = {"url": None}
                    
                continue
            
            # Format property
            try:
                properties[notion_prop_name] = self._format_property(notion_type, value)
            except Exception as e:
                print(f"Error formatting property '{col}': {str(e)}")
                # Use appropriate defaults
                if notion_type == "title":
                    properties[notion_prop_name] = {"title": [{"text": {"content": str(value)[:100]}}]}
                else:
                    properties[notion_prop_name] = {"rich_text": [{"text": {"content": str(value)[:100]}}]}
        
        # Ensure we have a title property
        if "Job Role" not in [prop_data["notion_prop_name"] for col, prop_data in NOTION_SCHEMA.items() if col in properties]:
            job_title = row_dict.get("job_position_title", "Unknown Job")
            # Find the title property name from schema
            title_prop_name = next((prop_data["notion_prop_name"] for col, prop_data in NOTION_SCHEMA.items() 
                                 if prop_data["type"] == "title"), "Job Role")
            properties[title_prop_name] = {"title": [{"text": {"content": job_title}}]}
        
        return properties

    @staticmethod
    def _format_property(notion_type: str, value: Any) -> Dict[str, Any]:
        """Format a property for Notion based on its type"""
        try:
            if notion_type == "title":
                return {"title": [{"text": {"content": str(value)}}]}
            elif notion_type == "rich_text":
                return {"rich_text": [{"text": {"content": str(value)}}]}
            elif notion_type == "number":
                return {"number": float(value) if pd.notna(value) else None}
            elif notion_type == "select":
                # Handle empty values and ensure string
                if pd.isna(value) or value == "":
                    return {"select": {"name": "Not specified"}}
                return {"select": {"name": str(value).replace(",", "-")}}
            elif notion_type == "multi_select":
                # Handle empty values and ensure list of dicts
                if pd.isna(value) or value == "":
                    return {"multi_select": []}
                # For string input, split by comma
                if isinstance(value, str):
                    items = [item.strip() for item in value.split(',') if item.strip()]
                    return {"multi_select": [{"name": item} for item in items]}
                # For list input
                elif isinstance(value, list):
                    return {"multi_select": [{"name": str(item)} for item in value]}
                # Default case
                return {"multi_select": []}
            elif notion_type == "date":
                if pd.isna(value) or value == "":
                    return {"date": None}
                return {"date": {"start": str(value), "time_zone": "America/Montreal"}}
            elif notion_type == "checkbox":
                if pd.isna(value) or value == "":
                    return {"checkbox": False}
                return {"checkbox": bool(value)}
            elif notion_type == "url":
                if pd.isna(value) or value == "":
                    return {"url": None}
                return {"url": str(value)}
            else:
                # Default to rich_text for unknown types
                return {"rich_text": [{"text": {"content": str(value)}}]}
        except Exception as e:
            print(f"Error in _format_property for type {notion_type}: {str(e)}")
            # Return safe default
            return {"rich_text": [{"text": {"content": str(value)[:100]}}]}

    def add_detailed_content(self, page_id: str, row: pd.Series) -> None:
        blocks = self._create_content_blocks(row)
        self.notion.blocks.children.append(page_id, children=blocks)

    @staticmethod
    def _create_content_blocks(row: pd.Series) -> List[Dict[str, Any]]:
        blocks = []
        sections = [
            ("Job Description", row.get('job_description', '')),
            ("Why This Company", row.get('why_this_company', '')),
            ("Why Me", row.get('why_me', ''))
        ]

        for title, content in sections:
            if pd.isna(content) or content == "":
                continue  # Skip empty sections
                
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": title}}]
                }
            })
            blocks.extend(NotionManager._create_paragraph_blocks(content))

        return blocks

    @staticmethod
    def _create_paragraph_blocks(content: str) -> List[Dict[str, Any]]:
        blocks = []
        
        # Handle possible NaN or None values
        if pd.isna(content) or content is None:
            content = ""
            
        content = str(content)  # Ensure content is a string
        
        while content:
            block_content = content[:2000]
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": block_content}}]
                }
            })
            content = content[2000:]
        return blocks

    def one_way_sync(self, df: pd.DataFrame) -> None:
        self.sync_to_notion(df)

if __name__ == "__main__":
    # Example usage
    pass