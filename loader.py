import pandas as pd

def load_events(csv_path):
    df = pd.read_csv(csv_path)                           # ← Read CSV into DataFrame
    df['timestamp'] = pd.to_datetime(                    # ← Parse timestamps
        df['timestamp'], utc=True, errors='coerce'
    )
    df['duration_ms'] = df['duration_ms'].astype('Int64')  # ← Nullable integer
    return df

if __name__ == '__main__':
    df = load_events('video_events_sample.csv')
    print(f"Loaded {len(df)} rows of video events")      # ← Confirm it worked
    print(f"Columns: {list(df.columns)}")
