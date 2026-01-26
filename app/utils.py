import pandas as pd
import pdfplumber
import os
import uuid

def process_data_and_generate_report(file_path, ext, base_dir):
    df = None
    
    if ext == ".csv":
        try:
            df = pd.read_csv(file_path)
        except:
            # Try with different encoding or separator if needed
             df = pd.read_csv(file_path, encoding='latin1')
    elif ext == ".xlsx":
        df = pd.read_excel(file_path)
    elif ext == ".pdf":
        df = extract_table_from_pdf(file_path)
        
    if df is None or df.empty:
        raise Exception("Could not extract data from file or file is empty.")
        
    # Basic Cleaning
    df.columns = [str(c).strip() for c in df.columns]
    
    # Fix currency columns
    for col in df.columns:
        if df[col].dtype == 'object':
            sample = df[col].dropna().astype(str).head(10)
            if any(sample.str.contains(r'^\$|€|£', regex=True)):
                df[col] = df[col].replace(r'[$,]', '', regex=True)
                df[col] = pd.to_numeric(df[col], errors='coerce')

    # Generate Lightweight HTML Report
    # Return HTML string directly instead of saving to file (for Vercel)
    return generate_html_report(df)
    
    return report_filename

def extract_table_from_pdf(file_path):
    # This is a heuristic approach. extracting tables from PDF is hard.
    # We will try to extract the largest table found on first few pages
    all_rows = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                # table is list of lists
                # Assume first row is header if we haven't found one, or append
                if table:
                    # Clean None values
                    cleaned_table = [[cell if cell is not None else "" for cell in row] for row in table]
                    all_rows.extend(cleaned_table)
                    
    if not all_rows:
        return None
        
    # Assume first row is header
    header = all_rows[0]
    data = all_rows[1:]
    
    # Handle duplicates in header
    seen = {}
    unique_header = []
    for col in header:
        col_str = str(col).strip()
        if col_str in seen:
            seen[col_str] += 1
            unique_header.append(f"{col_str}_{seen[col_str]}")
        else:
            seen[col_str] = 0
            unique_header.append(col_str)
            
    df = pd.DataFrame(data, columns=unique_header)
    return df

def generate_html_report(df):
    # Statistics
    desc = df.describe().to_html(classes="table table-striped", border=0)
    head = df.head(10).to_html(classes="table table-striped", border=0)
    
    # Missing values
    missing = df.isnull().sum().to_frame(name='Missing Values')
    missing = missing[missing['Missing Values'] > 0]
    if not missing.empty:
        missing_html = missing.to_html(classes="table table-striped", border=0)
    else:
        missing_html = "<p>No missing values found.</p>"
        
    # Column types
    dtypes = df.dtypes.to_frame(name='Data Type').astype(str).to_html(classes="table table-striped", border=0)

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Analysis Report</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
        <style>
            :root {{
                --primary: #000000;
                --accent: #0071e3;
                --bg: #f5f5f7;
                --card-bg: #ffffff;
                --text: #1d1d1f;
                --border: #d2d2d7;
            }}
            body {{
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                background: var(--bg);
                color: var(--text);
                line-height: 1.5;
                margin: 0;
                padding: 40px 20px;
            }}
            .container {{
                max-width: 1000px;
                margin: 0 auto;
            }}
            h1 {{
                font-size: 32px;
                font-weight: 600;
                margin-bottom: 24px;
                color: var(--primary);
            }}
            h2 {{
                font-size: 24px;
                font-weight: 600;
                margin-top: 40px;
                margin-bottom: 16px;
                color: var(--primary);
            }}
            .card {{
                background: var(--card-bg);
                border-radius: 18px;
                padding: 32px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.05);
                overflow-x: auto;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                font-size: 14px;
            }}
            th {{
                text-align: left;
                padding: 12px;
                border-bottom: 1px solid var(--border);
                color: var(--secondary-text);
                font-weight: 600;
            }}
            td {{
                padding: 12px;
                border-bottom: 1px solid #eee;
            }}
            tr:last-child td {{
                border-bottom: none;
            }}
            .btn {{
                display: inline-block;
                padding: 10px 20px;
                background: var(--accent);
                color: white;
                text-decoration: none;
                border-radius: 980px;
                font-size: 14px;
                font-weight: 500;
                margin-bottom: 40px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/" class="btn">&larr; Back to Upload</a>
            <h1>Data Analysis Report</h1>
            
            <div class="card">
                <h2>Dataset Overview</h2>
                <p><strong>Rows:</strong> {df.shape[0]} | <strong>Columns:</strong> {df.shape[1]}</p>
                <div style="margin-top: 20px;">
                    {dtypes}
                </div>
            </div>

            <h2>Descriptive Statistics</h2>
            <div class="card">
                {desc}
            </div>

            <h2>First 10 Rows</h2>
            <div class="card">
                {head}
            </div>
            
            <h2>Missing Values</h2>
            <div class="card">
                {missing_html}
            </div>
        </div>
    </body>
    </html>
    """
    
    return html_content

