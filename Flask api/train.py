import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from datetime import datetime

# Load dataset
df = pd.read_csv("updated_inventory.csv")
df = df.dropna()

# Convert Date column to datetime
df["date"] = pd.to_datetime(df["date"])

# Time-based features
df["Month"] = df["date"].dt.month
df["DayOfWeek"] = df["date"].dt.dayofweek
df["IsWeekend"] = df["DayOfWeek"].apply(lambda x: 1 if x >= 5 else 0)

# Add trending data if available
try:
    trending_df = pd.read_csv('trending_products.csv')
    trending_counts = trending_df['product_name'].value_counts().reset_index()
    trending_counts.columns = ['item_name', 'trend_score']
    df = df.merge(trending_counts, on='item_name', how='left')
    df['trend_score'] = df['trend_score'].fillna(0)
except FileNotFoundError:
    df['trend_score'] = 0

# Feature engineering
numeric_features = ["Available Stock", "Stocks_bought", "trend_score"]
categorical_features = ["Month", "DayOfWeek", "IsWeekend"]

preprocessor = ColumnTransformer(
    transformers=[
        ('num', StandardScaler(), numeric_features),
        ('cat', OneHotEncoder(handle_unknown='ignore'), categorical_features)
    ])

# Model pipeline
model = Pipeline(steps=[
    ('preprocessor', preprocessor),
    ('regressor', RandomForestRegressor(
        n_estimators=200,
        max_depth=15,
        min_samples_split=3,
        random_state=42,
        n_jobs=-1))
])

# Train-test split
X = df[numeric_features + categorical_features]
y = df["Items_sold"]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train model
model.fit(X_train, y_train)

# Evaluate
train_score = model.score(X_train, y_train)
test_score = model.score(X_test, y_test)
mae = mean_absolute_error(y_test, model.predict(X_test))

print(f"✅ Model trained - Train R²: {train_score:.2f}, Test R²: {test_score:.2f}, MAE: {mae:.2f}")

# Save model
joblib.dump(model, "rf_sales.pkl")
