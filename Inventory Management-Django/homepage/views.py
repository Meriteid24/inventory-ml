import requests
from django.db.models import Sum
from django.shortcuts import render
from django.views.generic import View, TemplateView
from inventory.models import Stock
from transactions.models import SaleBill, PurchaseBill
from django.http import JsonResponse
from .ml_input import generate_ml_input_data
from django.utils import timezone
from .fetch_predictions import fetch_and_save_predictions  # 👈 NEW: fetch from the clean file


# ML API integration function for instant suggestions (shown in dashboard)
def get_ml_suggestions():
    try:
        df = generate_ml_input_data()

        # Add today's date to each item
        today_str = timezone.now().strftime("%Y-%m-%d")
        for item in df:
            item["date"] = today_str

        print("Sending to ML API:", df[:1])  # Debug first item

        response = requests.post(
            "http://127.0.0.1:5000/predict_bulk",
            json=df,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )

        response.raise_for_status()
        suggestions = response.json()

        return suggestions

    except requests.exceptions.RequestException as e:
        print(f"API request failed: {str(e)}")
        return [{"Item_Name": "Error", "Suggestion": "API connection failed"}]
    except Exception as e:
        print(f"Processing failed: {str(e)}")
        return [{"Item_Name": "Error", "Suggestion": f"Processing error: {str(e)}"}]


# API route to return inventory status
def get_inventory_data(request):
    return JsonResponse({'status': 'OK'})


# Admin dashboard view
class HomeView(View):
    template_name = "home.html"

    def get(self, request):
        # Step 1: Fetch and save latest ML predictions automatically
        fetch_and_save_predictions()

        # Step 2: Regular inventory and transaction data
        labels = []
        data = []

        stockqueryset = Stock.objects.filter(is_deleted=False).order_by('-quantity')
        for item in stockqueryset:
            labels.append(item.name)
            data.append(item.quantity)

        sales = SaleBill.objects.order_by('-time')[:3]
        purchases = PurchaseBill.objects.order_by('-time')[:3]

        # Step 3: Get live ML suggestions
        suggestions = get_ml_suggestions()

        context = {
            'labels': labels,
            'data': data,
            'sales': sales,
            'purchases': purchases,
            'suggestions': suggestions
        }
        return render(request, self.template_name, context)


# Static About page
class AboutView(TemplateView):
    template_name = "about.html"

from django.contrib.auth import logout
from django.shortcuts import redirect

def logout_view(request):
    logout(request) 

# Logout view
def logout_view(request):
    logout(request)  # This logs the user out
    return redirect('logout-success')  # Redirect to the logout success page (the logout.html)

from django.contrib.auth import logout
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

def logout_view(request):
    if request.method == 'POST':  # Ensure logout only happens via POST
        logout(request)  # Log the user out
        return redirect('home')  # Redirect to home page
    else:
        return HttpResponseForbidden("Forbidden: Logout request must be POST")  # Return an error if GET request is made
