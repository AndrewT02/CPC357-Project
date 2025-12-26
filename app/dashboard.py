import streamlit as st
from pymongo import MongoClient
import pandas as pd
import time

# --- CONFIGURATION ---
MONGO_URI = "mongodb+srv://teeandrew86_db_user:V7nnJejzgK28PXxx@project1.s2ihw2y.mongodb.net/?appName=Project1"

# Connect to Database
client = MongoClient(MONGO_URI)
db = client['smart_city_db']
collection = db['sensor_logs']

st.title("🚦 Smart Street Light Dashboard (MongoDB)")

# Auto-refresh button
if st.button('Refresh Data'):
    st.rerun()

# 1. Fetch Data from MongoDB (Get last 100 records, newest first)
cursor = collection.find().sort("timestamp", -1).limit(100)
data = list(cursor)

if data:
    # Convert to Pandas DataFrame for easy charting
    df = pd.DataFrame(data)
    
    # metrics need the absolute latest reading
    latest = df.iloc[0] 

    # Layout Metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Current Brightness", f"{latest['brightness']}%")
    col2.metric("Motion Detected", "YES" if latest['motion'] == 1 else "NO")
    col3.metric("Light Level", f"{latest['ldr']}")

    # Charts need time on the X-axis
    st.subheader("Brightness History")
    st.line_chart(df.set_index('timestamp')['brightness'])

    st.subheader("Motion Activity")
    st.bar_chart(df.set_index('timestamp')['motion'])
    
    # Show raw data table (Optional, good for debugging)
    with st.expander("View Raw Data"):
        st.dataframe(df)

else:
    st.warning("No data found in MongoDB yet. Start your Feather S3!")