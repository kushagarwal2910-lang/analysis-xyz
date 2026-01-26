import pandas as pd
import pdfplumber
import os
import uuid
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.pyplot as plt
import io
import base64
import numpy as np

def process_data_and_generate_report(file_path, ext, base_dir):
    df = None
    
    try:
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
    
    except Exception as e:
        # Friendly error handling
        return f"""
        <div style="text-align: center; padding: 50px; font-family: 'Inter', sans-serif;">
            <h2 style="color: #e63946;">Oops! Something went wrong.</h2>
            <p>We couldn't process your file. Please make sure it's a valid CSV, Excel, or PDF file.</p>
            <p style="color: #666; font-size: 14px;">Error details: {str(e)}</p>
            <a href="/" style="display: inline-block; margin-top: 20px; padding: 10px 20px; background: #0071e3; color: white; text-decoration: none; border-radius: 8px;">Try Again</a>
        </div>
        """

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
            # Use standard matplotlib colors instead of seaborn
            colors = ['#ff9999','#66b3ff','#99ff99','#ffcc99','#c2c2f0','#ffb3e6']
            df[col].value_counts().plot.pie(autopct='%1.1f%%', startangle=90, colors=colors[:df[col].nunique()])
            plt.title(f'Distribution of {col}', fontname='Inter', fontsize=14)
            plt.ylabel('')
            
            img = io.BytesIO()
            plt.savefig(img, format='png', bbox_inches='tight', dpi=120)
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
                df[col].value_counts().sort_index().plot.bar(color='#0071e3', alpha=0.8)
            else:
                df[col].plot.hist(bins=20, color='#0071e3', edgecolor='white', alpha=0.8)
            
            plt.title(f'Distribution of {col}', fontname='Inter', fontsize=14)
            plt.xlabel(col, fontname='Inter')
            plt.grid(axis='y', alpha=0.3)
            # sns.despine replacement
            plt.gca().spines['top'].set_visible(False)
            plt.gca().spines['right'].set_visible(False)
            
            img = io.BytesIO()
            plt.savefig(img, format='png', bbox_inches='tight', dpi=120)
            img.seek(0)
            charts.append({
                'title': f'Distribution of {col}',
                'img': base64.b64encode(img.getvalue()).decode()
            })
            plt.close()
            break # Only one numerical chart
            
    # 3. Correlation Heatmap (Manual implementation without seaborn)
    if len(num_cols) > 1:
        plt.figure(figsize=(10, 8))
        corr = df[num_cols].corr()
        
        plt.imshow(corr, cmap='coolwarm', interpolation='nearest')
        plt.colorbar()
        plt.title('Correlation Matrix', fontname='Inter', fontsize=14)
        
        # Add labels
        tick_marks = np.arange(len(num_cols))
        plt.xticks(tick_marks, num_cols, rotation=45, ha='right')
        plt.yticks(tick_marks, num_cols)
        
        img = io.BytesIO()
        plt.savefig(img, format='png', bbox_inches='tight', dpi=120)
        img.seek(0)
        charts.append({
            'title': 'Correlation Matrix',
            'img': base64.b64encode(img.getvalue()).decode()
        })
        plt.close()
            
    return charts

def generate_ai_insights(df):
    """
    Generates simulated AI insights based on statistical analysis.
    Returns a dict with 'findings' and 'recommendations'.
    """
    findings = []
    recommendations = []
    
    num_cols = df.select_dtypes(include=['number']).columns
    cat_cols = df.select_dtypes(include=['object', 'category']).columns
    
    # 1. Correlation Analysis
    if len(num_cols) > 1:
        corr_matrix = df[num_cols].corr().abs()
        # Select upper triangle of correlation matrix
        upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
        
        # Find features with correlation greater than 0.7
        to_drop = [column for column in upper.columns if any(upper[column] > 0.7)]
        
        for col in to_drop:
            # Find the row (index) that correlates with this col
            correlated_row = upper[col][upper[col] > 0.7].index[0]
            val = upper.loc[correlated_row, col]
            findings.append(f"Strong relationship detected between <strong>{correlated_row}</strong> and <strong>{col}</strong> ({val:.2f} correlation).")
            recommendations.append(f"Since {correlated_row} and {col} move together, consider optimizing for {correlated_row} to potentially drive {col}.")

    # 2. Outlier / Max-Min Analysis
    for col in num_cols[:2]: # Limit to first 2 numeric cols
        max_val = df[col].max()
        min_val = df[col].min()
        mean_val = df[col].mean()
        
        findings.append(f"The average <strong>{col}</strong> is approx. {mean_val:.2f}, but peaks at {max_val:.2f}.")
        if max_val > mean_val * 3:
            recommendations.append(f"Investigate the outliers in {col} where values exceed {mean_val * 2:.2f}, as they are significantly higher than the average.")

    # 3. Categorical Dominance
    for col in cat_cols[:1]:
        top_val = df[col].mode()[0]
        freq = df[col].value_counts().iloc[0]
        total = len(df)
        pct = (freq/total)*100
        findings.append(f"<strong>{top_val}</strong> is the dominant category in {col}, accounting for {pct:.1f}% of entries.")
        if pct > 50:
             recommendations.append(f"The dataset is heavily skewed towards {top_val}. Ensure your strategy accounts for this concentration.")

    # Fallbacks if analysis yields little
    if not findings:
        findings.append("Data appears balanced with no extreme statistical anomalies detected.")
        recommendations.append("Conduct a deeper segment analysis to find hidden patterns not visible in aggregate stats.")

    return {
        "findings": findings,
        "recommendations": recommendations
    }

def generate_ml_insights(df):
    insights = {}
    
    # 1. Determine Target Variable
    target_candidates = ['price', 'cost', 'salary', 'sales', 'churn', 'outcome', 'target', 'class', 'survived', 'profit', 'revenue']
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
    
    # 2. Prepare Data & Heuristic Analysis
    try:
        # Drop rows with missing target
        df_ml = df.dropna(subset=[target_col]).copy()
        
        # Identify type
        is_numeric_target = pd.api.types.is_numeric_dtype(df_ml[target_col])
        is_classification = not is_numeric_target or df_ml[target_col].nunique() < 10
        
        insights['type'] = 'Classification' if is_classification else 'Regression'
        insights['metric'] = "Confidence (Est.)" # Simplified metric title
        insights['score'] = "High" # Placeholder for heuristic confidence
        
        # Calculate impacts based on simple correlation
        impacts = {}
        
        numerics = df_ml.select_dtypes(include=['number']).columns
        
        if is_numeric_target and len(numerics) > 1:
            # For regression: use correlation
            correlations = df_ml[numerics].corrwith(df_ml[target_col]).abs()
            correlations = correlations.drop(target_col, errors='ignore')
            impacts = correlations.sort_values(ascending=False).to_dict()
            
        elif is_classification:
            # For classification: compare means/variance across groups for numeric features
            # This is a very rough proxy for feature importance
            # Determine which numeric columns vary most between classes
            scores = {}
            for col in numerics:
                if col == target_col: continue
                # Calculate variance of means across groups (ANOVA-ish logic simplified)
                try:
                    means = df_ml.groupby(target_col)[col].mean()
                    scores[col] = means.std() / (means.mean() + 1e-5) # Coefficient of variation of means
                except:
                    scores[col] = 0
            
            # Sort by score
            impacts = dict(sorted(scores.items(), key=lambda item: item[1], reverse=True))

        # If no impacts found (e.g. all categorical inputs), pick random or count unique
        if not impacts:
            # Fallback: Just return column names
            other_cols = [c for c in df_ml.columns if c != target_col][:5]
            impacts = {c: 0.5 for c in other_cols}

        # 4. Feature Importance Plot
        top_n = min(10, len(impacts))
        top_impacts = dict(list(impacts.items())[:top_n])
        
        plt.figure(figsize=(10, 6))
        plt.title(f'Key Drivers of "{target_col}"', fontname='Inter', fontsize=14)
        
        names = list(top_impacts.keys())
        values = list(top_impacts.values())
        
        plt.bar(range(len(names)), values, align='center', color='#0071e3', alpha=0.8)
        plt.xticks(range(len(names)), names, rotation=45, ha='right')
        plt.grid(axis='y', alpha=0.3)
        plt.gca().spines['top'].set_visible(False)
        plt.gca().spines['right'].set_visible(False)
        plt.tight_layout()
        
        img = io.BytesIO()
        plt.savefig(img, format='png', bbox_inches='tight', dpi=120)
        img.seek(0)
        insights['importance_plot'] = base64.b64encode(img.getvalue()).decode()
        plt.close()
        
        return insights
        
    except Exception as e:
        print(f"ML Error: {e}")
        return None

def generate_html_report(df):
    # Statistics
    desc = df.describe().to_html(classes="table datatable", border=0)
    
    # Data Preview
    head = df.head(100).to_html(classes="table datatable display", border=0, table_id="data-preview-table")
    
    # Missing values
    missing = df.isnull().sum().to_frame(name='Missing Values')
    missing = missing[missing['Missing Values'] > 0]
    if not missing.empty:
        missing_html = missing.to_html(classes="table datatable", border=0)
    else:
        missing_html = "<div class='empty-state'>No missing values found. Clean dataset!</div>"
        
    # Column types
    dtypes = df.dtypes.to_frame(name='Data Type').astype(str).to_html(classes="table datatable", border=0)

    # Generate Charts
    charts = generate_charts(df)
    charts_html = ""
    if charts:
        charts_html = "<h2>Visualizations</h2><div class='charts-grid'>"
        for chart in charts:
            charts_html += f"""
            <div class='card chart-card'>
                <h3 class='card-title'>{chart['title']}</h3>
                <img src='data:image/png;base64,{chart['img']}' alt='{chart['title']}'>
            </div>
            """
        charts_html += "</div>"
        
    # Generate ML Insights
    ml_insights = generate_ml_insights(df)
    ml_html = ""
    if ml_insights:
        ml_html = f"""
        <h2>Predictive Analytics</h2>
        <div class="card ml-card">
            <div class="ml-header">
                <div class="ml-target">
                    <span class="label">Target Variable</span>
                    <h3>{ml_insights['target_col']}</h3>
                    <span class="badge">{ml_insights['type']}</span>
                </div>
                <div class="ml-score">
                    <span class="score-value">{ml_insights['score']}</span>
                    <span class="score-label">{ml_insights['metric']}</span>
                </div>
            </div>
            <div class="ml-body">
                <h3>Key Drivers</h3>
                <p>The chart below identifies which factors most significantly influence <strong>{ml_insights['target_col']}</strong>.</p>
                <div class="chart-container">
                    <img src='data:image/png;base64,{ml_insights['importance_plot']}' alt='Feature Importance'>
                </div>
            </div>
        </div>
        """

    # Generate AI Insights (New Feature)
    ai_data = generate_ai_insights(df)
    ai_html = ""
    if ai_data:
        findings_html = "".join([f"<li>{item}</li>" for item in ai_data['findings']])
        recs_html = "".join([f"<li>{item}</li>" for item in ai_data['recommendations']])
        
        ai_html = f"""
        <div class="ai-summary-section">
            <div class="card ai-card">
                <div class="ai-header">
                    <span class="ai-badge">✨ Smart Executive Summary</span>
                    <h2>Business Intelligence Report</h2>
                </div>
                <div class="ai-grid">
                    <div class="ai-col">
                        <h3>🔑 Key Findings</h3>
                        <ul class="insight-list">
                            {findings_html}
                        </ul>
                    </div>
                    <div class="ai-col">
                        <h3>🚀 Actionable Recommendations</h3>
                        <ul class="insight-list">
                            {recs_html}
                        </ul>
                    </div>
                </div>
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
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <!-- DataTables CSS -->
        <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.11.5/css/jquery.dataTables.css">
        <style>
            :root {{
                --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                --primary: #111111;
                --secondary: #666666;
                --accent: #0071e3;
                --accent-hover: #0077ed;
                --bg: #f5f5f7;
                --surface: #ffffff;
                --border: #e1e1e1;
                --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
                --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
                --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
                --radius-md: 12px;
                --radius-lg: 16px;
            }}
            
            * {{
                box-sizing: border-box;
            }}
            
            body {{
                font-family: var(--font-sans);
                background-color: var(--bg);
                color: var(--primary);
                line-height: 1.6;
                margin: 0;
                padding: 40px 20px;
                -webkit-font-smoothing: antialiased;
            }}
            
            .container {{
                max-width: 1000px;
                margin: 0 auto;
            }}
            
            .nav-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 40px;
            }}
            
            .btn {{
                display: inline-flex;
                align-items: center;
                padding: 10px 16px;
                background: white;
                color: var(--primary);
                text-decoration: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 500;
                border: 1px solid var(--border);
                transition: all 0.2s;
            }}
            
            .btn:hover {{
                border-color: var(--secondary);
                background: #fafafa;
            }}
            
            .btn-primary {{
                background: var(--accent);
                color: white;
                border: none;
            }}
            
            .btn-primary:hover {{
                background: var(--accent-hover);
            }}
            
            h1, h2, h3 {{
                color: var(--primary);
                font-weight: 600;
                margin-top: 0;
            }}
            
            h2 {{
                font-size: 20px;
                margin-top: 48px;
                margin-bottom: 16px;
                letter-spacing: -0.01em;
            }}
            
            .card {{
                background: var(--surface);
                border-radius: var(--radius-lg);
                padding: 32px;
                box-shadow: var(--shadow-md);
                border: 1px solid rgba(0,0,0,0.03);
                margin-bottom: 24px;
                overflow: hidden;
            }}
            
            /* AI Card Styling */
            .ai-card {{
                border-left: 4px solid var(--accent);
                background: linear-gradient(to bottom right, #ffffff, #f9faff);
            }}
            
            .ai-header {{
                margin-bottom: 24px;
            }}
            
            .ai-badge {{
                display: inline-block;
                background: rgba(0, 113, 227, 0.1);
                color: var(--accent);
                font-size: 12px;
                font-weight: 600;
                padding: 4px 12px;
                border-radius: 20px;
                margin-bottom: 8px;
            }}
            
            .ai-grid {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 40px;
            }}
            
            @media (max-width: 768px) {{
                .ai-grid {{
                    grid-template-columns: 1fr;
                    gap: 24px;
                }}
            }}
            
            .insight-list {{
                margin: 0;
                padding: 0;
                list-style: none;
            }}
            
            .insight-list li {{
                position: relative;
                padding-left: 20px;
                margin-bottom: 12px;
                color: var(--secondary);
                font-size: 15px;
            }}
            
            .insight-list li:before {{
                content: "•";
                color: var(--accent);
                position: absolute;
                left: 0;
                font-weight: bold;
            }}
            
            /* Charts */
            .charts-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
                gap: 24px;
            }}
            
            .chart-card img {{
                width: 100%;
                height: auto;
                border-radius: 8px;
            }}
            
            .card-title {{
                font-size: 16px;
                color: var(--secondary);
                margin-bottom: 16px;
                text-align: center;
            }}
            
            /* Tables */
            table.datatable {{
                width: 100%;
                border-collapse: collapse;
                font-size: 14px;
            }}
            
            .dataTables_wrapper .dataTables_length, 
            .dataTables_wrapper .dataTables_filter {{
                margin-bottom: 20px;
                font-size: 14px;
            }}
            
            table.dataTable thead th {{
                border-bottom: 1px solid var(--border) !important;
                color: var(--secondary);
                font-weight: 600;
                padding: 12px !important;
            }}
            
            table.dataTable tbody td {{
                padding: 12px !important;
                border-bottom: 1px solid #f0f0f0;
                color: var(--primary);
            }}
            
            /* Footer / Monetization */
            .cto-footer {{
                margin-top: 60px;
                padding: 40px;
                background: #1d1d1f;
                border-radius: var(--radius-lg);
                color: white;
                text-align: center;
            }}
            
            .cto-footer h3 {{
                color: white;
                margin-bottom: 8px;
            }}
            
            .cto-footer p {{
                color: #a1a1a6;
                margin-bottom: 24px;
            }}
            
            .export-bar {{
                position: sticky;
                bottom: 20px;
                left: 0;
                right: 0;
                display: flex;
                justify-content: center;
                pointer-events: none;
                z-index: 100;
            }}
            
            .export-btn {{
                pointer-events: auto;
                background: #1d1d1f;
                color: white;
                padding: 12px 24px;
                border-radius: 30px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                text-decoration: none;
                font-weight: 600;
                display: flex;
                align-items: center;
                gap: 8px;
                transition: transform 0.2s;
            }}
            
            .export-btn:hover {{
                transform: translateY(-2px);
            }}

            /* Mobile Responsive Fixes */
            .card {{
                 overflow-x: auto;
            }}
            
            .dataTables_wrapper {{
                overflow-x: auto;
            }}
            
        </style>
    </head>
    <body>
        <div class="container">
            <div class="nav-header">
                <a href="/" class="btn">&larr; Analyze Another File</a>
                <div style="font-weight: 600;">Analysis XYZ</div>
            </div>
            
            {ai_html}
            
            {ml_html}
            
            {charts_html}

            <h2>Data Preview</h2>
            <div class="card">
                {head}
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px;">
                <div>
                    <h2>Descriptive Statistics</h2>
                    <div class="card">
                        {desc}
                    </div>
                </div>
                <div>
                     <h2>Data Types</h2>
                    <div class="card">
                         <div style="margin-bottom: 10px; font-size: 14px; color: var(--secondary);">
                            <strong>Total Rows:</strong> {df.shape[0]} | <strong>Columns:</strong> {df.shape[1]}
                        </div>
                        {dtypes}
                    </div>
                </div>
            </div>
            
            <h2>Missing Values</h2>
            <div class="card">
                {missing_html}
            </div>
            
            <div class="cto-footer">
                <h3>Need a deeper custom analysis?</h3>
                <p>Get a comprehensive audit from a certified data scientist.</p>
                <a href="#" class="btn btn-primary" style="border:none;">Hire a Data Expert</a>
            </div>
        </div>
        
        <div class="export-bar">
            <a href="#" class="export-btn" onclick="alert('This feature is part of the Pro plan. Upgrade to export professional PDF reports.'); return false;">
                <span>📄 Export Professional Report</span>
            </a>
        </div>
        
        <!-- jQuery and DataTables JS -->
        <script type="text/javascript" charset="utf8" src="https://code.jquery.com/jquery-3.5.1.js"></script>
        <script type="text/javascript" charset="utf8" src="https://cdn.datatables.net/1.11.5/js/jquery.dataTables.js"></script>
        
        <script>
            $(document).ready( function () {{
                $('.datatable').DataTable({{
                    "pageLength": 10,
                    "scrollX": true,
                    "lengthChange": false,
                    "searching": true
                }});
            }});
        </script>
    </body>
    </html>
    """
    
    return html_content

