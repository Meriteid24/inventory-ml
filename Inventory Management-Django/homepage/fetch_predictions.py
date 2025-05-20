from inventory.models import Stock
from transactions.models import MLPrediction, InventoryItem
from django.utils import timezone
import requests

def fetch_and_save_predictions():
    try:
        stock_items = Stock.objects.all()
        payload = []
        for item in stock_items:
            payload.append({
                "item_name": item.name,
                "Available Stock": item.quantity,  
                "Stocks_bought": getattr(item, 'stocks_bought_recently', 0) or 0,  
                "Date": timezone.now().date().isoformat(),
            })

        if not payload:
            print("⚠️ No stock items found.")
            return

        # Call Flask API
        response = requests.post(
            "http://127.0.0.1:5000/predict_bulk",
            json=payload,
            timeout=15
        )

        if response.status_code != 200:
            print(f"Flask API Error: {response.text}")
            return

        predictions = response.json()

        # Save predictions
        for pred in predictions:
            item_name = pred["item_name"]
            predicted_sold = pred["Predicted_Items_Sold"]
            suggested_order = pred["Suggested_Order"]

            # Find InventoryItem 
            inventory_item = InventoryItem.objects.filter(name=item_name).first()
            if inventory_item:
                MLPrediction.objects.create(
                    item=inventory_item,
                    predicted_sales=predicted_sold,
                    suggested_order=suggested_order,
                    input_features=pred,  # full raw prediction dictionary
                    model_version="v1",   # or your model version
                    is_trending=predicted_sold > inventory_item.current_stock  # example trending logic
                )

        print("Predictions saved successfully.")

    except Exception as e:
        print(f"Django Fetch Error: {str(e)}")
