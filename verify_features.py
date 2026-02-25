from app.db.session import SessionLocal
from app.services.feature_engineering import prepare_training_data
import pandas as pd

def main():
    session = SessionLocal()

    category = "Edible Oil"   # change to test others
    X, y, df = prepare_training_data(session, category)

    print("\n===== SHAPES =====")
    print("X shape:", X.shape)
    print("y shape:", y.shape)
    print("df shape:", df.shape)

    print("\n===== HEAD =====")
    print(df.head())

    print("\n===== NULL CHECK =====")
    print(df.isnull().sum())

    print("\n===== COLUMN LIST =====")
    print(df.columns)

    from app.models.festival import Festival
    session = SessionLocal()
    print(session.query(Festival).all())

    session.close()

    import matplotlib.pyplot as plt

    plt.figure(figsize=(12,4))
    plt.plot(df["date"], df["festival_score"])
    plt.title("Festival Score Over Time")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
