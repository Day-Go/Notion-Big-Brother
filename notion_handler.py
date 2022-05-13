import time
from utils import get_date_and_time
from notion.client import NotionClient
from notion.block import HeaderBlock, TableBlock, CollectionViewBlock, ColumnBlock, ColumnListBlock 
from notion_client import Client

def format_column_blocks(page):
    # Create a list of columns
    col_list = page.children.add_new(ColumnListBlock)

    # Populate list with two columns
    col1 = col_list.children.add_new(ColumnBlock)
    col2 = col_list.children.add_new(ColumnBlock)

    # Add heading to each column
    col1kid = col1.children.add_new(
        HeaderBlock, title="Tracker"
    )
    col2kid = col2.children.add_new(
        HeaderBlock, title="Summary"
    )

    return col1, col2

def get_collection_schema():
    return {
        "title": {"name": "Date", "type": "title"},
        "=d{|": {"name": "Total time (m)", "type": "number"},
        "4Jv$": {"name": "Most used app", "type": "text"},
    }

def get_page_schema(date):
    return {
        "Date": {"title": [{"text": {"content": date}}]}
    }

class Notion():
    def __init__(self, gui, attr_list) -> None:
        self.date, _ = get_date_and_time()

        attr_dict = {}
        for attr in attr_list:
            attr_dict.update({attr: getattr(gui, attr)})

        self.params = attr_dict["params"]
        self.console_writer = attr_dict["console_writer"]

        # We use both clients since notion-py is more complete but no longer supported
        #   sdk -> https://github.com/ramnes/notion-sdk-py
        #   py  -> https://github.com/jamalex/notion-py
        self.client_sdk = Client(auth=self.params["notion_sdk_token"])
        self.client_py = NotionClient(token_v2=self.params["notion_py_token"])

        self.root_page = self.client_py.get_block(self.params["root_url"]) 

        self.database, self.table = None, None
        self.database_entry = []

        self.search_workspace()

        if self.database is None and self.table is None:
            self.create_workspace()

        self.search_database()

        if not self.database_entry:
            self.create_database_entry()

        # creating database entries uses sdk which does not return a block object
        self.database_entry = self.client_py.get_block(self.database_entry['url'])

    def search_workspace(self):
        self.console_writer.write("Searching for existing workspace.")

        # Find all blocks that contain the database name
        db_results = self.client_py.search_blocks(self.params["db_name"], limit=50)
        # and table name
        tb_results = self.client_py.search_blocks(self.params["tb_name"], limit=50) 


        for result in db_results:
            parent = result.parent
            grand_parent = parent.parent
            great_grand_parent = grand_parent.parent 
            if isinstance(result, CollectionViewBlock) and great_grand_parent.id == self.root_page.id:
                self.database = result
                self.console_writer.write(f"Existing database found.")

        for result in tb_results:
            parent = result.parent
            grand_parent = parent.parent
            great_grand_parent = grand_parent.parent 
            if isinstance(result, TableBlock) and great_grand_parent.id == self.root_page.id:
                self.table = result
                self.console_writer.write(f"Existing table found.")

    def create_workspace(self):
        self.console_writer.write("No workspace found.")
        
        page = self.client_py.get_block(self.params["root_url"])
        self.console_writer.write(f"Creating new workspace at {self.params['root_url']}.")

        col1, col2 = format_column_blocks(page)

        self.create_database(col1)
        self.create_table(col2)

    def create_database(self, parent):
        self.database = parent.children.add_new(CollectionViewBlock)
        self.database.collection = self.client_py.get_collection(
            self.client_py.create_record("collection", parent=self.database, schema=get_collection_schema())
        )
        self.database.title = self.params["db_name"]
        self.database.views.add_new(view_type="table")
        self.console_writer.write(f"Database ready.")

    def create_table(self, parent):
        self.table = parent.children.add_new(TableBlock)
        self.table.title = self.params["tb_name"]
        self.table.set_columns(3)
        self.table.add_row(["Total time (m)", "Most used app", "Most used app time (m)"])
        self.table.add_row([])
        self.console_writer.write(f"Table ready.")

    def search_database(self):
        self.console_writer.write(f"Searching for {self.date} database entry.")
        db_search_filter = {
            "property": "Date",
            "rich_text": {
                "contains": self.date
            }
        }

        result = self.client_sdk.databases.query(
            database_id =  self.database.id,
            filter = db_search_filter,
        )

        if result["results"]:
            self.database_entry = result.get("results")[0]
            self.console_writer.write(f"{self.date} entry found.")

    def create_database_entry(self):
        self.console_writer.write(f"No database entry found. Creating entry for {self.date}.")
        page_properties = get_page_schema(self.date)

        self.database_entry = self.client_sdk.pages.create(
            parent = {
                "database_id": self.database.id,
            },
            properties = page_properties 
        )
        self.console_writer.write(f"Database entry created.")