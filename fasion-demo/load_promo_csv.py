# load_csv.py
import csv
import os
import ecom_llm
from hdbcli import dbapi
# from gen_ai_hub.proxy.native.openai import embeddings  
# from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain_google_genai import GoogleGenerativeAIEmbeddings #ADDED
#from ecom_llm import get_sapGenAI_embedding as get_embedding
#from ecom_llm import get_sapGenAI_embedding as get_embedding
from ecom_llm import get_google_embedding as get_embedding

#from ecom_llm import sap_generative_ai_llm as llm

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

#Promotion data load starts

def load_promotion_csv_data(csv_file_path: str, table_name: str):
    """
    Load promotion data from a CSV file into the specified table in SAP HANA.
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
            PROMO_ID NVARCHAR(36) PRIMARY KEY,
            PROMO_PRODUCT_ID NVARCHAR(255),
            PROMO_PRODUCT_NAME NVARCHAR(255),            
            PROMO_TITLE NVARCHAR(255),
            PROMO_DESCRIPTION NVARCHAR(255),
            PROMO_DISCOUNT_PERCENT NVARCHAR(255),
            PROMO_START_DATE NVARCHAR(255),
            PROMO_END_DATE NVARCHAR(255),
            VECTOR_PROMO_PRODUCT_NAME REAL_VECTOR,  -- Vector attribute for PROMO_PRODUCT_NAME
            VECTOR_PROMO_DISCOUNT_PERCENT REAL_VECTOR, -- Vector attribute for PROMO_DISCOUNT_PERCENT
            VECTOR_PROMO_END_DATE REAL_VECTOR -- Vector attribute for PROMO_END_DATE
            
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
            promo_id = str(row[0]).strip() if len(row) > 0 and row[0] else f"MISSING_{row[0]}"
            promo_product_id = str(row[1]).strip() if len(row) > 1 and row[1] else "Unknown Product"
            promo_product_name = str(row[2]).strip() if len(row) > 2 and row[2] else "No product name"
            promo_title = str(row[3]).strip() if len(row) > 3 and row[3] else "No promo title"
            promo_description = str(row[4]).strip() if len(row) > 4 and row[4] else "No promo description"
            promo_discount_percent = str(row[5]).strip() if len(row) > 5 and row[5] else "No promo discount"
            promo_start_date = str(row[6]).strip() if len(row) > 6 and row[6] else "No promo start date"
            promo_end_date = str(row[7]).strip() if len(row) > 7 and row[7] else "No promo end date"

            # Remove trailing commas to avoid tuple creation
            vector_promo_product_name = get_embedding(promo_product_name)
            vector_promo_discount_percent = get_embedding(promo_discount_percent)
            vector_promo_end_date = get_embedding(promo_end_date)

            # Correct INSERT SQL
            insert_sql = f"""
            INSERT INTO {table_name} (
                PROMO_ID, PROMO_PRODUCT_ID, PROMO_PRODUCT_NAME, PROMO_TITLE, PROMO_DESCRIPTION,
                PROMO_DISCOUNT_PERCENT, PROMO_START_DATE, PROMO_END_DATE,
                VECTOR_PROMO_PRODUCT_NAME, VECTOR_PROMO_DISCOUNT_PERCENT, VECTOR_PROMO_END_DATE
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """

            cursor.execute(insert_sql, (
                promo_id, promo_product_id, promo_product_name, promo_title, promo_description,
                promo_discount_percent, promo_start_date, promo_end_date,
                vector_promo_product_name, vector_promo_discount_percent, vector_promo_end_date
            ))

    conn.commit()
    cursor.close()
    conn.close()
    print(f"Data loaded into {table_name} from {csv_file_path}")
#Promotion data load Ends



if __name__ == "__main__":    
     drop_table_if_exists("SAP_PROMOTION_COMMERCE_2211_V2")
     load_promotion_csv_data("data/product_promotion_v2.csv", "SAP_PROMOTION_COMMERCE_2211_V2")



    