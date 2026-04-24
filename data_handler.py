import pandas as pd
import random

def load_data():
    return pd.read_csv("parking_data.csv")

def simulate_slots(df):
    df['available_slots'] = df['available_slots'].apply(
        lambda x: max(0, x + random.randint(-3, 3))
    )
    return df