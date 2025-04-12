import pytest
from fastapi.testclient import TestClient
from main import app  # Replace 'main' with your module name where app is declared

client = TestClient(app)

@pytest.fixture
def sample_payload():
    # Replace these URLs and emails with your test endpoints or known good test values
    return {
    "scrape_url": "https://docs.google.com/spreadsheets/d/18UoIYMIzRXZzsWX12oTsEk13W3jTA9oTd_kT-iSQb4c/edit",
    "keyword_url": "https://docs.google.com/spreadsheets/d/1CvPneSUomXjHwcfqNJS_zYCukpq0AjxpYnczWkGuDqw/edit",
    "amazon_url": "https://docs.google.com/spreadsheets/d/1A3SW1gqTQrB0Z5jGm0PcNQJnw2IcGFHuZd1aRPLt8ZQ/edit",
    "product_url": "https://www.naturesustained.com/products/natural-shampoo?variant=44673198489761",
    "emails": "alizamankhan152@gmail.com"
}

def test_trigger_endpoint(sample_payload):
    # Run the /trigger endpoint once
    response = client.post("/trigger", json=sample_payload)
    print("Response status code:", response.status_code)
    print("Response content:", response.json())
    assert response.status_code == 200, f"Unexpected status code: {response.status_code}"
    data = response.json()
    # Check expected keys in the response
    assert "google_sheets" in data
    assert "google_docs" in data
