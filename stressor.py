import time
import json
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# Update the URL to your deployed endpoint (or use localhost for local testing)
url = "http://localhost:8000/trigger"

# Your test payload with known good URLs and parameters.
payload = {
    "scrape_url": "https://docs.google.com/spreadsheets/d/18UoIYMIzRXZzsWX12oTsEk13W3jTA9oTd_kT-iSQb4c/edit",
    "keyword_url": "https://docs.google.com/spreadsheets/d/1CvPneSUomXjHwcfqNJS_zYCukpq0AjxpYnczWkGuDqw/edit",
    "amazon_url": "https://docs.google.com/spreadsheets/d/1A3SW1gqTQrB0Z5jGm0PcNQJnw2IcGFHuZd1aRPLt8ZQ/edit",
    "product_url": "https://www.naturesustained.com/products/natural-shampoo?variant=44673198489761",
    "emails": "alizamankhan152@gmail.com"
}

def send_request():
    try:
        response = requests.post(url, headers={"Content-Type": "application/json"}, data=json.dumps(payload))
        # Return status code and response content
        return response.status_code, response.json()
    except Exception as e:
        return None, str(e)

def main():
    # Configure how many requests and how many concurrent workers
    total_requests = 50
    max_workers = 10

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(send_request) for _ in range(total_requests)]
        for future in as_completed(futures):
            status, content = future.result()
            if status is None:
                print("Request failed with error:", content)
            else:
                print(f"Status Code: {status}, Response: {content}")
                
if __name__ == "__main__":
    main()
