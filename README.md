# Flask Bank Statement PDF Parser

A simple Flask API to parse Islami Bank Bangladesh PLC PDF statements and extract account info, transactions, and totals.

## 🧪 How to Use

### Locally:
1. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the app:
   ```bash
   python app.py
   ```

### API Endpoint:
`POST /parse-statement`  
Form-data:
- `file`: (attach PDF file)

### Output:
- JSON with account info, transactions, totals

## 🚀 Free Deployment

You can deploy this project on:

- [Render](https://render.com)
- [Replit](https://replit.com)
