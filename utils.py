import math

def calculate_distance(lat1, lon1, lat2, lon2):
    return math.sqrt((lat2 - lat1)**2 + (lon2 - lon1)**2)

def suggest_best(df):
    return df.sort_values(
        by=['available_slots', 'distance'],
        ascending=[False, True]
    ).iloc[0]