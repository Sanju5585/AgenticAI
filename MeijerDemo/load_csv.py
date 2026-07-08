# load_csv.py
import csv
import os
import ecom_llm
from hdbcli import dbapi
# from gen_ai_hub.proxy.native.openai import embeddings  
# from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain_google_genai import GoogleGenerativeAIEmbeddings #ADDED
from ecom_llm import get_google_embedding as get_embedding
from ecom_llm import google_generative_ai_llm as llm

def connect_to_hana():
    """
    Establish a connection to SAP HANA Vector DB.
    Make sure to set the environment variables or directly set these values.
    """
    conn = dbapi.connect(
        address='794d7a51-4a96-4b97-a476-dacb3a0440b4.hna2.prod-eu10.hanacloud.ondemand.com',
        port='443',
        user='00F588CD78904954BA0FA8C9585A169F_8C04J77WXE7NPHALBEVGEC4AA_DT',
        password='Ae7Z34V2HG_8_j8r1kb_dWJsCGEnmE_nN0Z0cMULba.EdRcYbilznUf.bsX-ZJJ9q.9_13It90i_q3n8jSzE8zF_gfHbwEuE9LJos0bENwD2Q6YJjo_TlBICY23muSi.',
        encrypt=True,
        autocommit=True,
        sslValidateCertificate=False,
    )
    return conn

def drop_table_if_exists(table_name: str):
    """
    Drop the specified table if it exists in SAP HANA.
    """
    conn = connect_to_hana()
    cursor = conn.cursor()

    # Check if the table exists
    check_table_query = f"""
    SELECT COUNT(*) 
    FROM TABLES 
    WHERE TABLE_NAME = '{table_name}'
    """
    cursor.execute(check_table_query)
    table_exists = cursor.fetchone()[0]

    # Drop the table if it exists
    if table_exists > 0:
        drop_table_query = f"DROP TABLE {table_name}"
        cursor.execute(drop_table_query)
        conn.commit()
        print(f"Table {table_name} dropped.")

    cursor.close()
    conn.close()

def load_product_csv_data(csv_file_path: str, table_name: str):
    """
    Load data from a CSV file into the specified table in SAP HANA.
    Assumes the table already exists or creates it if it does not.
    """
    conn = connect_to_hana()
    cursor = conn.cursor()

    # Check if the table exists
    check_table_query = f"""
    SELECT COUNT(*) 
    FROM TABLES 
    WHERE TABLE_NAME = '{table_name}'
    """
    cursor.execute(check_table_query)
    table_exists = cursor.fetchone()[0]

    # Create the table if it does not exist
    if table_exists == 0:
        create_table_query = f"""
        CREATE TABLE {table_name} (
            PRODUCT_ID NVARCHAR(36) PRIMARY KEY,
            PRODUCT_NAME NVARCHAR(255),
            SUMMARY NVARCHAR(5000),
            PRICE DECIMAL(10,2),
            CATEGORY_IDs NVARCHAR(255),
            IMAGE_URL NVARCHAR(5000),
            VECTOR_NAME REAL_VECTOR,  -- Vector attribute for NAME (768 dimensions from Google)
            VECTOR_SUMMARY REAL_VECTOR  -- Vector attribute for DESCRIPTION (768 dimensions)
        )
        """
        cursor.execute(create_table_query)
        conn.commit()
        print(f"Table {table_name} created.")

    # Load data from the CSV file into the table
    with open(csv_file_path, "r", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader)  # Read the header row
        for row in reader:
            product_id, product_name, summary, price, CATEGORY_IDs,IMAGE_URL = row
            vector_product_name = get_embedding(product_name)
            vector_summary = get_embedding(summary)
            check_sql=f"""
            SELECT COUNT(*) FROM {table_name} WHERE PRODUCT_ID = ?
            """
            cursor.execute(check_sql, (product_id,))
            exists = cursor.fetchone()[0]
            if exists == 0:
                # Insert data into the table
                insert_sql = f"""
                INSERT INTO {table_name} (
                PRODUCT_ID, PRODUCT_NAME, SUMMARY, PRICE, CATEGORY_IDs, IMAGE_URL, VECTOR_NAME, VECTOR_SUMMARY
                ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?
                )
                """
                cursor.execute(insert_sql, (product_id, product_name, summary, price, CATEGORY_IDs, IMAGE_URL, vector_product_name, vector_summary))

    conn.commit()
    cursor.close()
    conn.close()

def load_order_csv_data(csv_file_path: str, table_name: str):
    """
    Load order data from a CSV file into the specified table in SAP HANA.
    Assumes the table already exists or creates it if it does not.
    """
    conn = connect_to_hana()
    cursor = conn.cursor()

    # Check if the table exists
    check_table_query = f"""
    SELECT COUNT(*) 
    FROM TABLES 
    WHERE TABLE_NAME = '{table_name}'
    """
    cursor.execute(check_table_query)
    table_exists = cursor.fetchone()[0]

    # Create the table if it does not exist
    if table_exists == 0:
        create_table_query = f"""
        CREATE TABLE {table_name} (
            ORDER_ID NVARCHAR(36) PRIMARY KEY,
            CUSTOMER_ID NVARCHAR(36),
            TOTAL_PRICE NVARCHAR(255),
            PRODUCT_ID NVARCHAR(36),
            PRODUCT_NAME NVARCHAR(255),
            ORDER_STATUS NVARCHAR(255),
            ORDER_DATE NVARCHAR(255),
            VECTOR_PRODUCT_NAME REAL_VECTOR  -- Vector attribute for PRODUCT_NAME
        )
        """
        cursor.execute(create_table_query)
        conn.commit()
        print(f"Table {table_name} created.")

    # Load data from the CSV file into the table
    with open(csv_file_path, "r", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader)  # Read the header row
        for row in reader:
            # Extract values from the row
            order_id, customer_id, total_price, product_id, product_name, order_status, order_date = row

            # Generate vector for PRODUCT_NAME
            vector_product_name = get_embedding(product_name)

            # Insert data into the table
            insert_sql = f"""
            INSERT INTO {table_name} (
                ORDER_ID, CUSTOMER_ID, TOTAL_PRICE, PRODUCT_ID, PRODUCT_NAME, ORDER_STATUS, ORDER_DATE, VECTOR_PRODUCT_NAME
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?
            )
            """
            cursor.execute(insert_sql, (order_id, customer_id, total_price, product_id, product_name, order_status, order_date, vector_product_name))

    conn.commit()
    cursor.close()
    conn.close()
    print(f"Data loaded into {table_name} from {csv_file_path}")

def load_category_csv_data(csv_file_path: str, table_name: str):
    """
    Load category data from a CSV file into the specified table in SAP HANA.
    Assumes the table already exists or creates it if it does not.
    """
    conn = connect_to_hana()
    cursor = conn.cursor()

    # Check if the table exists
    check_table_query = f"""
    SELECT COUNT(*) 
    FROM TABLES 
    WHERE TABLE_NAME = '{table_name}'
    """
    cursor.execute(check_table_query)
    table_exists = cursor.fetchone()[0]

    # Create the table if it does not exist
    if table_exists == 0:
        create_table_query = f"""
        CREATE TABLE {table_name} (
            CATEGORY_NAME NVARCHAR(255),
            CATEGORY_ID NVARCHAR(36) PRIMARY KEY,
            VECTOR_CATEGORY_NAME REAL_VECTOR  -- Vector attribute for CATEGORY_NAME
        )
        """
        cursor.execute(create_table_query)
        conn.commit()
        print(f"Table {table_name} created.")

    # Load data from the CSV file into the table
    with open(csv_file_path, "r", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader)  # Read the header row
        for row in reader:
            category_name,category_id = row

            # Generate vector for CATEGORY_NAME
            vector_category_name = get_embedding(category_name)

            # Insert data into the table
            insert_sql = f"""
            INSERT INTO {table_name} (
                CATEGORY_NAME, CATEGORY_ID, VECTOR_CATEGORY_NAME
            ) VALUES (
                ?, ?, ?
            )
            """
            cursor.execute(insert_sql, (category_name, category_id, vector_category_name))

    conn.commit()
    cursor.close()
    conn.close()
    print(f"Data loaded into {table_name} from {csv_file_path}")

def load_customer_csv_data(csv_file_path: str, table_name: str):
    """
    Load customer data from a CSV file into the specified table in SAP HANA.
    Assumes the table already exists or creates it if it does not.
    """
    conn = connect_to_hana()
    cursor = conn.cursor()

    # Check if the table exists
    check_table_query = f"""
    SELECT COUNT(*) 
    FROM TABLES 
    WHERE TABLE_NAME = '{table_name}'
    """
    cursor.execute(check_table_query)
    table_exists = cursor.fetchone()[0]

    # Create the table if it does not exist
    if table_exists == 0:
        create_table_query = f"""
        CREATE TABLE {table_name} (
            CUSTOMER_ID NVARCHAR(36) PRIMARY KEY,
            CUSTOMER_NAME NVARCHAR(255),
            GENDER NVARCHAR(10),
            AGE INT,
            VECTOR_CUSTOMER_NAME REAL_VECTOR  -- Vector attribute for CUSTOMER_NAME
        )
        """
        cursor.execute(create_table_query)
        conn.commit()
        print(f"Table {table_name} created.")

    # Load data from the CSV file into the table
    with open(csv_file_path, "r", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader)  # Read the header row
        for row in reader:
            customer_name, customer_id, gender, age = row

            # Generate vector for CUSTOMER_NAME
            vector_customer_name = get_embedding(customer_name)

            # Insert data into the table
            insert_sql = f"""
            INSERT INTO {table_name} (
                CUSTOMER_ID, CUSTOMER_NAME, GENDER, AGE, VECTOR_CUSTOMER_NAME
            ) VALUES (
                ?, ?, ?, ?, ?
            )
            """
            cursor.execute(insert_sql, (customer_id, customer_name, gender, int(age), vector_customer_name))

    conn.commit()
    cursor.close()
    conn.close()
    print(f"Data loaded into {table_name} from {csv_file_path}")

def load_faq_csv_data(csv_file_path: str, table_name: str):
    """
    Load FAQ data from a CSV file into the specified table in SAP HANA.
    Assumes the table already exists or creates it if it does not.
    """
    conn = connect_to_hana()
    cursor = conn.cursor()

    # Check if the table exists
    check_table_query = f"""
    SELECT COUNT(*) 
    FROM TABLES 
    WHERE TABLE_NAME = '{table_name}'
    """
    cursor.execute(check_table_query)
    table_exists = cursor.fetchone()[0]

    # Create the table if it does not exist
    if table_exists == 0:
        create_table_query = f"""
        CREATE TABLE {table_name} (
            QUESTION NVARCHAR(5000),
            ANSWER NVARCHAR(5000),
            VECTOR_QUESTION REAL_VECTOR  -- Vector attribute for QUESTION
        )
        """
        cursor.execute(create_table_query)
        conn.commit()
        print(f"Table {table_name} created.")

    # Load data from the CSV file into the table
    with open(csv_file_path, "r", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader)  # Read the header row
        for row in reader:
            question, answer = row

            # Generate vector for QUESTION
            vector_question = get_embedding(question)

            # Insert data into the table
            insert_sql = f"""
            INSERT INTO {table_name} (
                QUESTION, ANSWER, VECTOR_QUESTION
            ) VALUES (
                ?, ?, ?
            )
            """
            cursor.execute(insert_sql, (question, answer, vector_question))

    conn.commit()
    cursor.close()
    conn.close()
    print(f"Data loaded into {table_name} from {csv_file_path}")

# Get embeddings  
# def get_embedding(text: str) -> list:
#     try:
#         # Initialize GoogleGenerativeAIEmbeddings
#         embeddings_model = get_sapGenAI_embedding
#         embedding = embeddings_model.embed_query(text)  
#         return embedding
#     except Exception as e:
#         print(f"Error generating embedding: {e}")
#         return []
    


if __name__ == "__main__":
    # Load only product.csv into HANA DB with updated image URLs
    print("🚀 Loading product.csv with updated localhost image URLs into SAP_PRODUCTS_COMMERCE_2211_V2")
    print("=" * 80)
    
    drop_table_if_exists("SAP_PRODUCTS_COMMERCE_2211_V2")
    load_product_csv_data("data/product.csv", "SAP_PRODUCTS_COMMERCE_2211_V2")
    