from datetime import timedelta
from django.db.models import Sum
from inventory.models import Stock
from transactions.models import SaleItem, PurchaseItem
from django.utils import timezone

def generate_ml_input_data(use_pandas=False):
    recent_days = timezone.now() - timedelta(days=30)
    stock_items = Stock.objects.filter(is_deleted=False)

    data = []
    for item in stock_items:
        total_sold = SaleItem.objects.filter(
            stock=item,
            billno__time__gte=recent_days
        ).aggregate(total=Sum('quantity'))['total'] or 0

        total_bought = PurchaseItem.objects.filter(
            stock=item,
            billno__time__gte=recent_days
        ).aggregate(total=Sum('quantity'))['total'] or 0

        data.append({  # ✅ FIXED: now it's inside the loop
            'item_name': item.name,
            'Available Stock': item.quantity,
            'Stocks_bought': total_bought,
            'Date': timezone.now().strftime("%Y-%m-%d")
        })

    if not use_pandas:
        return data

    try:
        import pandas as pd
    except ImportError:
        raise ImportError("Pandas is required for DataFrame output. Install with: pip install pandas")

    df = pd.DataFrame(data)
    df['Available Stock'] = df['Available Stock'].astype(int)
    df['Stocks_bought'] = df['Stocks_bought'].astype(int)

    return df
