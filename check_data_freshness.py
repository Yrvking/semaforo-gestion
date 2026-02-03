
import os
import glob
import pandas as pd
from datetime import datetime

DOWNLOAD_DIR = r"C:\Users\Yrving\Downloads\CARPETA_SEMAFORO"

print(f"Checking data in: {DOWNLOAD_DIR}")

files = {
    'Prospectos': 'reporteProspectos.xlsx',
    'Ventas': 'ReporteVenta.xlsx',
    'Separaciones': 'Separacion.xlsx',
    'Visitas': 'ReporteVisitas.xlsx'
}

for name, filename in files.items():
    path = os.path.join(DOWNLOAD_DIR, filename)
    print(f"\n--- {name} ({filename}) ---")
    
    if not os.path.exists(path):
        print("❌ FILE NOT FOUND")
        continue
        
    try:
        df = pd.read_excel(path, engine='openpyxl')
        print(f"✅ Loaded {len(df)} rows")
        
        # Identify date columns
        date_cols = [c for c in df.columns if 'FECHA' in c.upper()]
        print(f"Date columns found: {date_cols}")
        
        if date_cols:
            # Pick the most likely "Creation Date"
            target_col = date_cols[0] 
            # Convert to datetime
            df[target_col] = pd.to_datetime(df[target_col], dayfirst=True, errors='coerce')
            
            min_date = df[target_col].min()
            max_date = df[target_col].max()
            
            print(f"Date Range in {target_col}: {min_date} to {max_date}")
        else:
            print("⚠️ No columns with 'Fecha' name found to verify freshness.")
            print(f"Columns: {list(df.columns)}")
            
    except Exception as e:
        print(f"❌ Error reading file: {e}")
