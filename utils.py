import requests


def fetch_product_name_online(barcode: str) -> str:
    """Look up a product name via OpenFoodFacts (free, no API key).

    Raises RuntimeError when the barcode is not found.
    """
    url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
    resp = requests.get(url, timeout=5)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") == 1 and data["product"].get("product_name"):
        return data["product"]["product_name"]
    raise RuntimeError("Nicht in OpenFoodFacts gefunden")
