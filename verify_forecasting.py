from app.db.session import SessionLocal
from app.services.forecasting import forecast_next_n_days

session = SessionLocal()

df_forecast = forecast_next_n_days(session, "Edible Oil", n_days=30)

print(df_forecast.head())
print(df_forecast.describe())