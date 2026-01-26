import pandas as pd
import pdfplumber
import os
import uuid
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import LabelEncoder
from sklearn.impute import SimpleImputer
import numpy as np

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

def generate_charts(df):
    charts = []
    
    # 1. Pie Chart for Categorical Data
    cat_cols = df.select_dtypes(include=['object', 'category']).columns
    for col in cat_cols:
        # Check if column has reasonable number of unique values for a pie chart
        if 1 < df[col].nunique() < 15:
            plt.figure(figsize=(8, 6))
            df[col].value_counts().plot.pie(autopct='%1.1f%%', startangle=90)
            plt.title(f'Distribution of {col}')
            plt.ylabel('')
            
            img = io.BytesIO()
            plt.savefig(img, format='png', bbox_inches='tight')
            img.seek(0)
            charts.append({
                'title': f'Distribution of {col}',
                'img': base64.b64encode(img.getvalue()).decode()
            })
            plt.close()
            break # Only one pie chart to avoid clutter
            
    # 2. Bar/Hist Chart for Numerical Data
    num_cols = df.select_dtypes(include=['number']).columns
    for col in num_cols:
        if df[col].nunique() > 1:
            plt.figure(figsize=(10, 6))
            if df[col].nunique() < 20:
                df[col].value_counts().sort_index().plot.bar(color='#0071e3')
            else:
                df[col].plot.hist(bins=20, color='#0071e3', edgecolor='white')
            
            plt.title(f'Distribution of {col}')
            plt.xlabel(col)
            plt.grid(axis='y', alpha=0.5)
            
            img = io.BytesIO()
            plt.savefig(img, format='png', bbox_inches='tight')
            img.seek(0)
            charts.append({
                'title': f'Distribution of {col}',
                'img': base64.b64encode(img.getvalue()).decode()
            })
            plt.close()
            break # Only one numerical chart
            
    # 3. Correlation Heatmap
    if len(num_cols) > 1:
        plt.figure(figsize=(10, 8))
        corr = df[num_cols].corr()
        sns.heatmap(corr, annot=True, cmap='coolwarm', fmt=".2f", linewidths=0.5)
        plt.title('Correlation Matrix')
        
        img = io.BytesIO()
        plt.savefig(img, format='png', bbox_inches='tight')
        img.seek(0)
        charts.append({
            'title': 'Correlation Matrix',
            'img': base64.b64encode(img.getvalue()).decode()
        })
        plt.close()
            
    return charts

def generate_ml_insights(df):
    insights = {}
    
    # 1. Determine Target Variable
    # Heuristic: Look for common target names, otherwise pick the last column
    target_candidates = ['price', 'cost', 'salary', 'sales', 'churn', 'outcome', 'target', 'class', 'survived']
    target_col = None
    
    # Check for exact matches first
    for col in df.columns:
        if col.lower() in target_candidates:
            target_col = col
            break
            
    # If no match, pick the last column that isn't an ID
    if not target_col:
        for col in reversed(df.columns):
            if 'id' not in col.lower() and df[col].nunique() > 1:
                target_col = col
                break
                
    if not target_col:
        return None

    insights['target_col'] = target_col
    
    # 2. Prepare Data
    try:
        # Drop rows with missing target
        df_ml = df.dropna(subset=[target_col]).copy()
        
        # Separate X and y
        X = df_ml.drop(columns=[target_col])
        y = df_ml[target_col]
        
        # Handle ID columns in X (drop them)
        cols_to_drop = [c for c in X.columns if 'id' in c.lower() or X[c].nunique() == len(X)]
        X = X.drop(columns=cols_to_drop)
        
        # Encode Categorical Variables
        le_dict = {}
        for col in X.select_dtypes(include=['object', 'category']).columns:
            if X[col].nunique() < 50: # Limit to reasonable cardinality
                le = LabelEncoder()
                X[col] = le.fit_transform(X[col].astype(str))
                le_dict[col] = le
            else:
                X = X.drop(columns=[col]) # Drop high cardinality columns
                
        # Handle Missing Values in X
        imputer = SimpleImputer(strategy='mean')
        X_imputed = pd.DataFrame(imputer.fit_transform(X), columns=X.columns)
        
        # 3. Choose Model & Train
        is_classification = False
        if pd.api.types.is_numeric_dtype(y) and y.nunique() > 10:
            # Regression
            model = RandomForestRegressor(n_estimators=50, random_state=42, max_depth=10)
            scoring = 'r2'
            insights['type'] = 'Regression'
        else:
            # Classification
            is_classification = True
            model = RandomForestClassifier(n_estimators=50, random_state=42, max_depth=10)
            scoring = 'accuracy'
            insights['type'] = 'Classification'
            
            # Encode y if needed
            if not pd.api.types.is_numeric_dtype(y):
                le_y = LabelEncoder()
                y = le_y.fit_transform(y.astype(str))
                
        # Cross Validation Score
        scores = cross_val_score(model, X_imputed, y, cv=3)
        insights['score'] = f"{scores.mean():.2f}"
        insights['metric'] = "Accuracy" if is_classification else "R² Score"
        
        # Fit on full data for feature importance
        model.fit(X_imputed, y)
        
        # 4. Feature Importance
        importances = model.feature_importances_
        indices = np.argsort(importances)[::-1]
        top_n = min(10, len(X.columns))
        
        plt.figure(figsize=(10, 6))
        plt.title(f'Top {top_n} Factors Influencing "{target_col}"')
        plt.bar(range(top_n), importances[indices[:top_n]], align='center', color='#0071e3')
        plt.xticks(range(top_n), [X.columns[i] for i in indices[:top_n]], rotation=45, ha='right')
        plt.tight_layout()
        
        img = io.BytesIO()
        plt.savefig(img, format='png', bbox_inches='tight')
        img.seek(0)
        insights['importance_plot'] = base64.b64encode(img.getvalue()).decode()
        plt.close()
        
        return insights
        
    except Exception as e:
        print(f"ML Error: {e}")
        return None

def generate_html_report(df):
    # Statistics
    desc = df.describe().to_html(classes="table table-striped", border=0)
    
    # Data Preview (Increased to 100 rows for better interaction)
    # We give it a specific ID for DataTables
    head = df.head(100).to_html(classes="table table-striped display", border=0, table_id="data-preview-table")
    
    # Missing values
    missing = df.isnull().sum().to_frame(name='Missing Values')
    missing = missing[missing['Missing Values'] > 0]
    if not missing.empty:
        missing_html = missing.to_html(classes="table table-striped", border=0)
    else:
        missing_html = "<p>No missing values found.</p>"
        
    # Column types
    dtypes = df.dtypes.to_frame(name='Data Type').astype(str).to_html(classes="table table-striped", border=0)

    # Generate Charts
    charts = generate_charts(df)
    charts_html = ""
    if charts:
        charts_html = "<h2>Visualizations</h2><div class='charts-grid'>"
        for chart in charts:
            charts_html += f"""
            <div class='card chart-card'>
                <h3>{chart['title']}</h3>
                <img src='data:image/png;base64,{chart['img']}' alt='{chart['title']}'>
            </div>
            """
        charts_html += "</div>"
        
    # Generate ML Insights
    ml_insights = generate_ml_insights(df)
    ml_html = ""
    if ml_insights:
        ml_html = f"""
        <h2>AI Prediction Insights</h2>
        <div class="card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <div>
                    <h3 style="margin: 0; color: var(--accent);">Target Variable: {ml_insights['target_col']}</h3>
                    <p style="margin: 5px 0 0 0; color: var(--secondary-text);">Task: {ml_insights['type']}</p>
                </div>
                <div style="text-align: right;">
                    <h3 style="margin: 0; font-size: 24px;">{ml_insights['score']}</h3>
                    <p style="margin: 5px 0 0 0; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">{ml_insights['metric']}</p>
                </div>
            </div>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
            <h3>What drives this outcome?</h3>
            <p>The chart below shows which factors have the most impact on <strong>{ml_insights['target_col']}</strong>.</p>
            <div style="text-align: center;">
                <img src='data:image/png;base64,{ml_insights['importance_plot']}' style="max-width: 100%; height: auto;" alt='Feature Importance'>
            </div>
        </div>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Analysis Report</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
        <!-- DataTables CSS -->
        <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.11.5/css/jquery.dataTables.css">
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
                margin-bottom: 24px;
            }}
            .charts-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
                gap: 24px;
            }}
            .chart-card {{
                display: flex;
                flex-direction: column;
                align-items: center;
            }}
            .chart-card img {{
                max-width: 100%;
                height: auto;
                margin-top: 16px;
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
                color: var(--text);
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
            
            {ml_html}
            
            {charts_html}

            <h2>Data Preview (First 100 Rows)</h2>
            <div class="card">
                {head}
            </div>

            <h2>Descriptive Statistics</h2>
            <div class="card">
                {desc}
            </div>
            
            <h2>Data Structure & Types</h2>
            <div class="card">
                <p><strong>Rows:</strong> {df.shape[0]} | <strong>Columns:</strong> {df.shape[1]}</p>
                <div style="margin-top: 20px;">
                    {dtypes}
                </div>
            </div>
            
            <h2>Missing Values</h2>
            <div class="card">
                {missing_html}
            </div>
        </div>
        
        <!-- jQuery and DataTables JS -->
        <script type="text/javascript" charset="utf8" src="https://code.jquery.com/jquery-3.5.1.js"></script>
        <script type="text/javascript" charset="utf8" src="https://cdn.datatables.net/1.11.5/js/jquery.dataTables.js"></script>
        
        <script>
            $(document).ready( function () {{
                $('#data-preview-table').DataTable({{
                    "pageLength": 10,
                    "scrollX": true
                }});
            }});
        </script>
    </body>
    </html>
    """
    
    return html_content

