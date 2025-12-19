#!/usr/bin/env python3
import pandas as pd

import sys
import os
import json

def convert_log(jsonl_path):
    if not os.path.exists(jsonl_path):
        print(f"Error: File {jsonl_path} not found.")
        return

    try:
        import pandas as pd
    except ImportError:
        print("Error: pandas is not installed. Please run 'pip install pandas'")
        return

    print(f"Converting {jsonl_path}...")

    try:
        # Read JSONL
        data = []
        with open(jsonl_path, 'r') as f:
            for line in f:
                if line.strip(): data.append(json.loads(line))
        
        if not data:
            print("Log file is empty.")
            return

        df = pd.DataFrame(data)
        
        # Base filename
        base_name = os.path.splitext(jsonl_path)[0]
        
        # Apple Numbers / Excel compatible CSV
        csv_path = f"{base_name}.csv"
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        print(f"-> Saved {csv_path}")
        
        # Excel
        xlsx_path = f"{base_name}.xlsx"
        df.to_excel(xlsx_path, index=False)
        print(f"-> Saved {xlsx_path}")
        
    except Exception as e:
        print(f"Conversion failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 convert_logs.py <path_to_jsonl>")
    else:
        convert_log(sys.argv[1])
