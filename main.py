import gspread
import uvicorn
import pandas as pd
import requests
from bs4 import BeautifulSoup
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from oauth2client.service_account import ServiceAccountCredentials
import openai
from googleapiclient.discovery import build
from google.oauth2 import service_account
from dotenv import load_dotenv
import os
import openai
from fastapi import FastAPI, HTTPException
from fastapi import FastAPI
from pydantic import BaseModel
import asyncio
import json
import re
import time

app = FastAPI()

class RequestData(BaseModel):
    scrape_url: str
    keyword_url: str
    amazon_url: str
    product_url: str
    emails: str

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
SCOPES = ["https://www.googleapis.com/auth/documents"]

credentials = {
    "type": os.getenv("type", ""),
    "project_id": os.getenv("project_id", ""),
    "private_key_id": os.getenv("private_key_id", ""),
    "private_key": os.getenv("private_key", "").replace('\\n', '\n'),  # Ensure correct newlines
    "client_email": os.getenv("client_email", ""),
    "client_id": os.getenv("client_id", ""),
    "auth_uri": os.getenv("auth_uri", ""),
    "token_uri": os.getenv("token_uri", ""),
    "auth_provider_x509_cert_url": os.getenv("auth_provider_x509_cert_url", ""),
    "client_x509_cert_url": os.getenv("client_x509_cert_url", ""),
    "universe_domain": os.getenv("universe_domain", "")
}
service_account_email = credentials["client_email"]

json_filename = "google_credentials.json"

with open(json_filename, "w") as json_file:
    json.dump(credentials, json_file, indent=4)
SERVICE_ACCOUNT_FILE =json_filename

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
docs_service = build("docs", "v1", credentials=credentials)

@app.get("/")
def read_root():
    return {"message": "Hello World"}

@app.get("/hi")
def hi():
    return {"message": "Hello World"}

@app.post("/title")
async def title(data:RequestData):
    try:
        title = await generate_amazon_title(data.product_url)
        return {"status": "success", "message": "Title generated successfully", "title":title}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering title: {e}")

@app.post("/description")
async def description(data:RequestData):
    try:
        description = await generate_amazon_description(data.product_url)
        return {"status": "success", "message": "description generated successfully", "description":description}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering description: {e}")

@app.post("/bullets")
async def bullets(data:RequestData):
    try:
        bullets = await generate_amazon_bullets(data.product_url)
        return {"status": "success", "message": "bullets generated successfully", "bullets":bullets}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering bullets: {e}")

@app.post("/keywords")
async def keywords(data:RequestData):
    try:
        keywords = await generate_amazon_backend_keywords(data.product_url)
        return {"status": "success", "message": "keywords generated successfully", "keywords":keywords}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering keywords: {e}")

@app.post("/structuredfields")
async def structuredfields(data:RequestData):
    try:
        # match_and_create_google_sheet(credentials_file, data.amazon_url, data.scrape_url, data.googlesheet_url, data.product_url)
        return {"status": "success", "message": "google sheet generated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering structuredfields: {e}")


@app.get("/trigger")
@app.post("/trigger")
async def trigger_functions(data: RequestData):
    try:
        # print("Generating Google Sheet:")
        print("Generating Google Sheet:")
        
        message = match_and_create_new_google_sheet(
            credentials_file, data.amazon_url, data.scrape_url, data.product_url, data.emails
        )
    
        doc_title = "Amazon OpenFields"
        doc_id, doc_url = create_new_google_doc(doc_title, credentials_file)
        make_sheet_public_editable(doc_id, credentials_file, data.emails, service_account_email)
        print("Generating Google Docs:")
        await generate_amazon_backend_keywords(data.product_url, doc_id)
        await generate_amazon_bullets(data.product_url, doc_id)
        await generate_amazon_description(data.product_url, doc_id)
        await generate_amazon_title(data.product_url, doc_id)
        print("Results Generated")
        return {
            "status": "success", 
            "google_sheets":message,
            "google_docs": doc_url
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering /trigger: {e}")

def make_sheet_public_editable(file_id: str, credentials_file: str, email: str, service_account_email: str):
    """
    - Gives editor access to the service account and all specified emails.
    - Makes the file viewable by anyone with the link.
    """
    try:
        creds = service_account.Credentials.from_service_account_file(
            credentials_file,
            scopes=["https://www.googleapis.com/auth/drive"]
        )
        drive_service = build('drive', 'v3', credentials=creds)

        # Grant editor access to the service account
        permission_sa = {
            'type': 'user',
            'role': 'writer',
            'emailAddress': service_account_email
        }
        drive_service.permissions().create(
            fileId=file_id,
            body=permission_sa,
            fields='id',
            sendNotificationEmail=False
        ).execute()
        print(f"✅ Editor access granted to service account: {service_account_email}")

        if email != service_account_email:
                permission_user = {
                    'type': 'user',
                    'role': 'writer',
                    'emailAddress': email
                }
                drive_service.permissions().create(
                    fileId=file_id,
                    body=permission_user,
                    fields='id',
                    sendNotificationEmail=False
                ).execute()
                print(f"✅ Editor access granted to: {email}")

        # Make the file viewable by anyone with the link
        permission_public = {
            'type': 'anyone',
            'role': 'reader'
        }
        drive_service.permissions().create(
            fileId=file_id,
            body=permission_public,
            fields='id'
        ).execute()
        print("🌐 Public viewer access enabled (anyone with the link can view).")

    except Exception as e:
        raise Exception(f"❌ Error setting permissions: {e}")

def append_to_google_doc(doc_id, text):
    try:
        print('append_to_google_doc')
        """Append text to a Google Doc."""
        requests = [
            {
                "insertText": {
                    "location": {"index": 1},
                    "text": text + "\n\n"
                }
            }
        ]
        docs_service.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()
    except Exception as e:
        raise Exception(f"❌ Error appending to Google Doc: {e}")

def authenticate_gspread(credentials_file):
    try:
        print('authenticate_gspread')
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        # creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
        creds = service_account.Credentials.from_service_account_file(credentials_file, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        raise Exception(f"❌ Error authenticating gspread: {e}")

def get_google_sheet_data(gc, sheet_url):
    try:
        print('get_google_sheet_data')
        sheet = gc.open_by_url(sheet_url).sheet1
        # df = get_as_dataframe(sheet, evaluate_formulas=True, skip_blank_rows=True)
        df = pd.DataFrame(sheet.get_all_records())
        return df.dropna(how="all")
    except Exception as e:
        raise Exception(f"❌ Error getting Google Sheet data: {e}")

def scrape_product_info(product_url, max_retries=5):
    headers = {"User-Agent": "Mozilla/5.0 (...)"}
    retries = 0
    while retries < max_retries:
        try:
            response = requests.get(product_url, headers=headers, timeout=5)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                all_text = soup.get_text(separator=" ").lower()
                return re.sub(r'\s+', ' ', all_text).strip()
            else:
                print(f"Status: {response.status_code}. Retrying ({retries+1}/{max_retries})...")
                retries += 1
                time.sleep(2)
        except Exception as e:
            print(f"Error: {e}. Retrying ({retries+1}/{max_retries})...")
            retries += 1
            time.sleep(2)
    print("Failed to scrape product info after maximum retries.")
    raise HTTPException(status_code=500, detail="Failed to scrape product info.")
    return None


def get_top_matches(product_info, field_name, field_value, possible_values):
    
    """Uses OpenAI to find the best matches for a given field from the product description."""

    try:
            
        ai_prompt = f"""
        You are an AI specializing in product attribute matching.

        ### Product Information:
        {product_info}

        ### Field Name:
        {field_name}

        ### Field Value (Reference from Amazon Sheet):
        {field_value}

        ### Possible Options (from the Google Sheet):
        {', '.join(possible_values)}

        ### Instructions:
        - Compare the field value against the product description.
        - From the possible options, pick up to **5 best matches** that are most relevant.
        - Output only the matches as a **comma-separated list** with no extra text.
        - If no good matches exist, return an **empty string**.
        -DONT WRITE "UNSTRUCTURED FIELDS" OR "EMPTY STRING" JUST LEAVE IT EMPTY!!!
        """

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": ai_prompt}]
        )

        content = response.choices[0].message.content.strip()
        if not content or content.lower() in ["empty string", "structured field", "none", "n/a"]:
            return [""] * 5

        matches = [m.strip() for m in content.split(",") if m.strip().lower() not in ["empty string", "structured field", "none", "n/a"]]
        return matches[:5] + [""] * (5 - len(matches))

    except Exception as e:
        raise Exception(f"❌ Error getting top matches: {e}")
        return [""]

# def get_top_matches(product_info, field_name, field_value, possible_values):
#     # print('get_top_matches')
    
#     """Uses OpenAI to find the best matches for a given field from the product description."""
#     ai_prompt = f"""
#     You are an AI specializing in product attribute matching.

#     ### Product Information:
#     {product_info}

#     ### Field Name:
#     {field_name}

#     ### Field Value (Reference from Amazon Sheet):
#     {field_value}

#     ### Possible Options (from the Google Sheet):
#     {', '.join(possible_values)}

#     ### Instructions:
#     - Compare the field value against the product description.
#     - From the possible options, pick up to **5 best matches** that are most relevant.
#     - Output only the matches as a **comma-separated list** with no extra text.
#     - If no good matches exist, return an **empty string**.
#     """

#     response = client.chat.completions.create(
#         model="gpt-4-turbo",
#         messages=[{"role": "user", "content": ai_prompt}]
#     )
    
    
#     content = response.choices[0].message.content.strip()
#     if not content:  
#         return [""] * 5
#     matches = content.split(", ")
#     return matches[:5] + [""] * (5 - len(matches))

def match_and_create_new_google_sheet(credentials_file: str, amazon_url: str, scrap_url: str, product_url: str, emails:str) -> str:
    """
    Creates a new Google Sheet, updates its sharing permissions, performs matching between two sheets,
    and outputs the data to the new spreadsheet.
    """

    try:
        # Authorize gspread and create a new spreadsheet
        gc = authenticate_gspread(credentials_file)
        new_sheet_title = "Optimized Backend Attributes"
        new_spreadsheet = gc.create(new_sheet_title)

        
        new_sheet_url = new_spreadsheet.url
        file_id = new_spreadsheet.id
        print(f"Created new spreadsheet with title '{new_sheet_title}' and ID: {file_id}")
        
        # Update sharing permissions so anyone with the link can edit
        make_sheet_public_editable(file_id, credentials_file,emails, service_account_email)
        
        # Get data from the provided Amazon and Scrap sheets
        amazon_df = get_google_sheet_data(gc, amazon_url)
        print("amazon_df",amazon_df)
        scrap_df = get_google_sheet_data(gc, scrap_url)
        print("scrap_df",scrap_df)
        scraped_text = scrape_product_info(product_url)
        print("scraped_text",scraped_text)

        if scraped_text is None:
            return "Scraping failed."
        
        # Find matching fields between the two sheetsnn
        print('before amazon_fields')
        amazon_fields = set(amazon_df.iloc[1:, 0].dropna())
        scrap_fields = set(scrap_df.iloc[1:, 0].dropna())
        matching_fields = list(amazon_fields.intersection(scrap_fields))
        if not matching_fields:
            return "No matching fields found."
        
        # Prepare data for output
        print('before matched_data')
        matched_data = {
            "Field Name": [],
            "Value": [],
            "AI Best Matched 1": [],
            "AI Best Matched 2": [],
            "AI Best Matched 3": [],
            "AI Best Matched 4": [],
            "AI Best Matched 5": []
        }
        for field in matching_fields:
            print('inside matched_data loop')

            matched_data["Field Name"].append(field)
            value = amazon_df.loc[amazon_df.iloc[:, 0] == field].iloc[:, 1].values
            matched_value = value[0] if len(value) > 0 else ""
            possible_options = scrap_df.loc[scrap_df.iloc[:, 0] == field].iloc[:, 1].dropna().tolist()
            ai_matches = get_top_matches(scraped_text, field, matched_value, possible_options)
            ai_matches = ai_matches[:5] + [""] * (5 - len(ai_matches))  # Ensure 5 matches
            
            matched_data["Value"].append(matched_value)
            matched_data["AI Best Matched 1"].append(ai_matches[0])
            matched_data["AI Best Matched 2"].append(ai_matches[1])
            matched_data["AI Best Matched 3"].append(ai_matches[2])
            matched_data["AI Best Matched 4"].append(ai_matches[3])
            matched_data["AI Best Matched 5"].append(ai_matches[4])
        
        matched_df = pd.DataFrame(matched_data)
        print('outside matched_data loop')
        
        # Write the DataFrame to the new spreadsheet (first worksheet)
        output_sheet = new_spreadsheet.sheet1
        values = [matched_df.columns.tolist()] + matched_df.values.tolist()
        output_sheet.insert_rows(values, row=1)
        print("Data written to new spreadsheet.")
        
        return f"{new_sheet_url}"
    
    except Exception as e:
        raise Exception(f"Error in match_and_create_new_google_sheet: {e}")

def create_new_google_doc(title: str, credentials_file: str):
    """
    Creates a new Google Doc with the given title using the Docs API.
    Returns the document ID and URL.
    """
    try:
        creds = service_account.Credentials.from_service_account_file(
            credentials_file,
            scopes=["https://www.googleapis.com/auth/documents", "https://www.googleapis.com/auth/drive"]
        )
        docs_service = build("docs", "v1", credentials=creds)
        body = {"title": title}
        doc = docs_service.documents().create(body=body).execute()
        doc_id = doc.get("documentId")
        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
        print(f"Created new document with title '{title}', ID: {doc_id}")
        return doc_id, doc_url
    except Exception as e:
        raise Exception(f"Error creating new Google Doc: {e}")


credentials_file = "google_credentials.json"
client = openai.OpenAI(api_key=api_key)

async def generate_amazon_title(product_url, doc_id):
    # doc_title = "Amazon Title Output"
    # doc_id, doc_url = create_new_google_doc(doc_title, credentials_file)
    # make_sheet_public_editable(doc_id, credentials_file)
   
    title_prompt = f"""
    You are an expert in writing Amazon product titles optimized for search and conversions.  
    Your task is to generate a compelling, keyword-rich title using the exact product details provided.  

    ### Important Instructions:
    - **Do not assume** the size, volume, or weight—use the exact details provided.  
     **ONLY use the words EXACTLY as they appear in the product name and description.**  
    - Extract the main **product name and brand** (if available).  
    - Include **size, volume (e.g., "9oz"), weight, material, and key features** exactly as they appear.  
    - Use commonly searched keywords relevant to the product.  
    - Keep it concise, **within Amazon's 200-character limit**.  
    - **JUST return the Amazon-style product title with no extra text.**  

    **URL:** {product_url}
    """

    try:
        response = await asyncio.to_thread(client.chat.completions.create,
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are an expert in writing Amazon product titles."},
                {"role": "user", "content": title_prompt}
            ]
        )
        title = response.choices[0].message.content.strip()
        print("Generated Amazon Product Title")
        append_to_google_doc(doc_id, f"Amazon Product Title:\n{title}")
        return title
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating title: {str(e)}")

async def generate_amazon_bullets(product_url, doc_id):
    # doc_title = "Amazon Title Output"
    # doc_id, doc_url = create_new_google_doc(doc_title, credentials_file)
    # make_sheet_public_editable(doc_id, credentials_file)

    bullets_prompt = f"""
    Act as an Amazon SEO expert. Extract **ONLY** verified product details from the provided data—no assumptions, no extra words.  
    Generate **five bullet points** highlighting the **key features and benefits** exactly as described in the product details.  

    ✅ **STRICT ACCURACY**: Use **only** words found in the product data. **Do NOT assume or invent features.**  
    ✅ **FIXED LENGTH**: Each bullet **must be between 210 and 230 characters EXCLUDING the capital words.**  
    ✅ **AMAZON COMPLIANT**: No false claims, redundancy, or keyword stuffing.  
    ✅ **SCANNABLE FORMAT**: Start each bullet with a **capitalized key feature** (e.g., `"DURABLE MATERIAL: High-quality..."`).  
    ✅ **READABILITY**: Use sentence case, keeping it clear and benefit-driven.  

    Write straight to the point and **do not include introductory text** like "here are bullet points." Each bullet should be **exactly** within the required character limit.

    Example Output:  
    ✔ **PREMIUM MATERIAL**: Made from ultra-soft, breathable cotton that enhances airflow and ensures a gentle touch on the skin. Provides superior comfort and long-lasting durability, making it ideal for sensitive skin and everyday wear.  

    ✔ **SUPERIOR FIT & COMFORT**: Expertly tailored for a snug yet flexible fit that adapts to movement without irritation. Designed for all-day comfort, making it perfect for work, travel, lounging, or an active lifestyle while maintaining breathability.  

    ✔ **DURABLE & LONG-LASTING**: High-quality fabric with reinforced stitching resists wear and tear, ensuring extended use without fading or shrinking. Retains softness, shape, and strength even after multiple washes, offering reliable durability over time.  

    ✔ **MOISTURE-WICKING TECHNOLOGY**: Advanced moisture-wicking fabric quickly absorbs sweat and allows it to evaporate, keeping you dry and fresh all day. Designed for workouts, hot climates, and daily wear, ensuring maximum breathability and temperature control.  

    ✔ **VERSATILE FOR ANY OCCASION**: Ideal for casual wear, workouts, travel, or lounging at home. Blends comfort and function effortlessly while pairing well with any outfit, making it a must-have staple that adapts to any season or setting with ease.  

    ### **Product Information:**  
    {product_url}  
    """
    try:
        response = await asyncio.to_thread(client.chat.completions.create,
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are an expert in writing Amazon product bullet points."},
                {"role": "user", "content": bullets_prompt}
            ]
        )
        bullets = response.choices[0].message.content.strip()
        print("Generated Amazon Bullet Points")
        append_to_google_doc(doc_id, f"Amazon Bullet Points:\n{bullets}")
        return bullets
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating bullets: {str(e)}")

async def generate_amazon_backend_keywords(product_url, doc_id):
    # doc_title = "Amazon Title Output"
    # doc_id, doc_url = create_new_google_doc(doc_title, credentials_file)
    # make_sheet_public_editable(doc_id, credentials_file)

    keywords_prompt = f"""
    please make sure to generate a total of 500 keywords, dont write more or less
    Amazon SEO Backend Keywords Prompt (500 Characters, No Repetition, High Conversion, Feature-Focused)
    Act as an Amazon SEO expert. Generate a backend keyword string of exactly 500 characters to maximize product discoverability while following Amazon’s guidelines.

    Instructions:
    1️⃣ Extract Unique, High-Relevance Keywords, No Repetition, High Conversion, Feature-Focused from keywords doc/product url whatever is available
    Dont assume anything, if its not written in the provided data then dont write it
    Remove redundant, closely related, or duplicate keywords (e.g., avoid both "organic shampoo" and "shampoo organic").

    2️⃣ Follow Amazon’s Backend Keyword Policies
    ✅ dont add any commas – Separate keywords with spaces.
    ✅ No competitor brand names, ASINs, or promotional claims (e.g., avoid "best shampoo," "top-rated").
    ✅ No redundant or overlapping keywords.

    3️⃣ Maximize Discoverability & Conversion Potential
    Include synonyms, regional spellings, and related terms customers might search for.
    Cover product variations, use cases, and relevant attributes (e.g., size, material, scent, key ingredients).
    Use alternative terms and phrasing to expand search reach.
    Maintain high relevance without repetition or unnecessary words.
    **Product Information:**
    {product_url}
    """

    try:
        if not product_url:
            return "Failed to generate backend keywords: No product data found"
        response = await asyncio.to_thread(client.chat.completions.create,
            model="gpt-4o",
            messages=[{"role": "user", "content": keywords_prompt}]
        )
        
        backend_keywords = response.choices[0].message.content.strip()
        print("Generated Amazon Product Keywords")
        backend_keywords = backend_keywords.replace(",", " ")  
        match = re.match(r'^(.{1,500})\b', backend_keywords)
        short_keywords = match.group(1) if match else backend_keywords[:500] 
        append_to_google_doc(doc_id, f"Amazon Keywords:\n{short_keywords}")


        return backend_keywords
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating keywords: {str(e)}")

async def generate_amazon_description(product_url, doc_id):
    # doc_title = "Amazon Title Output"
    # doc_id, doc_url = create_new_google_doc(doc_title, credentials_file)
    # make_sheet_public_editable(doc_id, credentials_file)

    description_prompt = f"""
    Act as an Amazon copywriting expert with 10+ years of experience crafting high-converting, SEO-optimized product
    descriptions that maximize visibility and drive sales.
    Your task is to generate a clear, engaging, and persuasive product description that highlights the product’s 
    unique features and key benefits while seamlessly integrating high-ranking keywords.
    Extract all product details ONLY from the provided URL—do NOT assume or fabricate any information.
    If an ingredient, feature, or specification is NOT mentioned, do not include it in the description.

    Instructions:
    ✅ USE SINGLE PARAGRAPH FOR WRITING, DONT INCLUDE NEXT LINES OR ICONS
    ✅ Identify key benefits, materials, specifications, and unique selling points while maintaining a professional and persuasive tone.
    ✅ Do NOT generate or invent customer reviews, quotes, or ratings.
    ✅ Use concise, benefit-driven bullet points to enhance readability.
    ✅ Ensure the description is SEO-optimized, short and to the point by naturally integrating relevant keywords.
    ✅ NO headings (e.g., "Product Description," "Key Features").
    How to Structure the Description:
    Start with a compelling hook that immediately captures attention.
    Clearly define what the product does and why it’s valuable
    Write 3-5 key benefits, keeping each concise yet impactful.
    Highlight 1-2 unique selling points that differentiate this product.
    Provide reassurance on quality, durability, and effectiveness.
    Now, generate a compelling Amazon product description based ONLY on verified product details. Do not fabricate ingredients, materials, reviews, or features that aren’t explicitly provided. 
    **Product Information:**
    {product_url}

    eg: Amazon Product Description: 
    Transform your hair care routine with our Natural Shampoo, crafted with the finest ingredients to deliver exceptional results. Gently cleanses hair without stripping natural oils, ensuring a fresh and healthy feel. Nourishes and strengthens hair from root to tip, enhancing overall texture and shine. Promotes a healthy scalp while preventing dryness and irritation, supporting long-term hair wellness. Infused with botanical extracts to provide a refreshing and revitalizing experience after every wash. Free from harsh chemicals, sulfates, and parabens, making it a safe and effective choice for all hair types. Formulated to uphold the highest standards of quality, ensuring long-lasting effectiveness and noticeable improvement in hair health. Elevate your hair care regimen with nature’s best ingredients.
 
 """
    try:
        """Generates an SEO-optimized Amazon product description."""
        if not product_url:
            return "Failed to generate product description: No product data found"
        response = await asyncio.to_thread(client.chat.completions.create,
            model="gpt-4o",
            messages=[{"role": "user", "content": description_prompt}]
        )
        
        optimized_description = response.choices[0].message.content.strip()
        print("Generated Amazon Product Description")
        append_to_google_doc(doc_id, f"Amazon Product Description:\n{optimized_description}")
        return optimized_description
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating description: {str(e)}")

credentials_file = "google_credentials.json"
client = openai.OpenAI(api_key=api_key)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
