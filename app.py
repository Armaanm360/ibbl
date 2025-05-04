from flask import Flask, request, jsonify
import pdfplumber
import re
from datetime import datetime
import traceback

app = Flask(__name__)

# Paste your full Flask parser code here
# ... (content skipped for brevity)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
