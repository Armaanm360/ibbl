from flask import Flask, request, jsonify
import pdfplumber
import re
from datetime import datetime
import traceback # Import traceback for detailed error logging

app = Flask(__name__)

def convert_date_format(date_str):
    """
    Convert date from various potential formats (DD/MM/YY, DD/MM/YYYY) to YYYY-MM-DD.
    Handles potential errors gracefully.
    """
    # Handle DD/MM/YY format (e.g., 01/03/25)
    try:
        date_obj = datetime.strptime(date_str, "%d/%m/%y")
        # Handle potential year 20xx vs 19xx ambiguity if needed, assuming 20xx
        # No change needed if strptime handles 'y' correctly based on context (usually does)
        return date_obj.strftime("%Y-%m-%d")
    except ValueError:
        pass # Try next format

    # Handle DD/MM/YYYY format (e.g., 01/03/2025)
    try:
        date_obj = datetime.strptime(date_str, "%d/%m/%Y")
        return date_obj.strftime("%Y-%m-%d")
    except ValueError:
        # Log or handle the error if the format is unexpected
        # print(f"Warning: Could not parse date '{date_str}'. Returning original.")
        return date_str # Return original string if all parsing fails


def parse_bank_statement(file_stream):
    """
    Parse Islami Bank Bangladesh PLC statement from PDF stream dynamically.
    """
    text = ""
    try:
        with pdfplumber.open(file_stream) as pdf:
            # Extract text from all pages
            text = "\n".join(page.extract_text() or "" for page in pdf.pages) # Added 'or ""' for safety
    except Exception as e:
        print(f"Error opening or reading PDF: {e}")
        raise # Re-raise the exception to be caught by the main handler

    # --- Account Information Extraction ---
    account_info = {"bank": "Islami Bank Bangladesh PLC."} # Default bank name
    try:
        # Use non-greedy matching and DOTALL for multi-line fields
        account_holder_match = re.search(r"Name\s+(.*?)\n", text) # Simpler match assuming name is first after "Name"
        address_match = re.search(r"Address\s+(.*?)\nAccount No", text, re.DOTALL) # Look for Address before Account No
        account_no_match = re.search(r"Account No\s+(\d+)", text)
        account_type_match = re.search(r"Account Type\s+(.*?)\n", text)
        period_match = re.search(r"Account Statement for the period of\s+(\d{2}/\d{2}/\d{4})\s+to\s+(\d{2}/\d{2}/\d{4})", text)

        account_info["account_holder"] = account_holder_match.group(1).strip() if account_holder_match else None
        # If address extraction needs refinement based on structure:
        # account_info["address"] = address_match.group(1).replace('\n', ' ').strip() if address_match else None # Example handling
        account_info["account_number"] = account_no_match.group(1) if account_no_match else None
        account_info["account_type"] = account_type_match.group(1).strip() if account_type_match else None

        if period_match:
            start_date_str = period_match.group(1).strip()
            end_date_str = period_match.group(2).strip()
            # Use the updated convert_date_format
            account_info["statement_period"] = {
                "start_date": convert_date_format(start_date_str),
                "end_date": convert_date_format(end_date_str)
            }
        else:
             account_info["statement_period"] = {"start_date": None, "end_date": None}

    except Exception as e:
        print(f"Error parsing account info: {e}")
        # Continue parsing transactions even if account info fails partially

    # --- Transaction Extraction ---
    transactions = []
    # More robust regex:
    # - Start of line anchor (^)? - Maybe not needed if splitting lines
    # - Date format DD/MM/YY: (\d{2}/\d{2}/\d{2})
    # - Whitespace: \s+
    # - Post Date: (\d{2}/\d{2}/\d{2}) # Capture Post Date early if it's consistently placed
    # - Description: (.+?) - Non-greedy
    # - Optional Instrument No: \s+([A-Z0-9]+)?
    # - Amounts (Withdrawal/Deposit/Balance): Allow optional comma, require decimal point. Use non-capturing group for comma part.
    #   Withdrawal: (\d{1,3}(?:,\d{3})*\.\d{2}|0\.00|\s*) - Allow empty/whitespace
    #   Deposit:    (\d{1,3}(?:,\d{3})*\.\d{2}|0\.00|\s*) - Allow empty/whitespace
    #   Balance:    (\d{1,3}(?:,\d{3})*\.\d{2})        - Balance seems mandatory
    # Using a simplified regex focusing on date, amounts, and balance based on common structure, letting description be flexible.
    # This Regex assumes: Trans Date, Post Date, Description..., Withdraw, Deposit, Balance
    # It allows for missing Instrument No and handles potentially empty Withdraw/Deposit fields.
    transaction_pattern = re.compile(
        r"(\d{2}/\d{2}/\d{2})\s+"      # Transaction Date (Group 1)
        r"(\d{2}/\d{2}/\d{2})\s+"      # Post Date (Group 2)
        r"(.*?)\s+"                   # Particulars/Description (Group 3 - non-greedy)
        # Lookahead to find the numeric section reliably
        r"(?=\d{1,3}(?:,\d{3})*\.\d{2}|0\.00|\s+\d{1,3}(?:,\d{3})*\.\d{2})"
        r"([A-Z0-9]+)?\s*"             # Optional Instrument No (Group 4) - moved after description
        r"(\d{1,3}(?:,\d{3})*\.\d{2}|0\.00)?\s+" # Withdrawal (Group 5) - optional
        r"(\d{1,3}(?:,\d{3})*\.\d{2}|0\.00)?\s+" # Deposit (Group 6) - optional
        r"(\d{1,3}(?:,\d{3})*\.\d{2})" # Balance (Group 7) - mandatory
    )


    lines = text.split('\n')
    for line in lines:
        # Skip headers or irrelevant lines more dynamically
        if "Trans Date" in line or "Post Date" in line or "Report taken on" in line or "B/F" in line or "Page" in line or not line.strip():
            continue

        match = transaction_pattern.match(line.strip())
        if match:
            try:
                trans_date, post_date, description, ref_no, withdraw, deposit, balance = match.groups()

                # Clean and convert values
                withdraw_str = (withdraw or "0.00").strip().replace(',', '')
                deposit_str = (deposit or "0.00").strip().replace(',', '')
                balance_str = (balance or "0.00").strip().replace(',', '')

                transactions.append({
                    "date": convert_date_format(trans_date),
                    "post_date": convert_date_format(post_date),
                    "description": description.strip(),
                    "reference": ref_no.strip() if ref_no else None,
                    "withdrawal": float(withdraw_str) if withdraw_str else 0.00,
                    "deposit": float(deposit_str) if deposit_str else 0.00,
                    "balance": float(balance_str) if balance_str else 0.00
                })
            except Exception as e:
                print(f"Error processing transaction line: '{line.strip()}' - {e}")
                # Optionally skip the problematic line or add partial data

    # --- Total Extraction ---
    # Look for the line starting with optional commas/whitespace then "TOTAL"
    # Capture the three numeric values after TOTAL
    total_match = re.search(r"^\s*(?:,*\s*)*TOTAL\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})", text, re.MULTILINE)
    totals = {"total_withdrawal": None, "total_deposit": None, "final_balance": None}
    if total_match:
        try:
            total_withdraw_str = total_match.group(1).replace(',', '')
            total_deposit_str = total_match.group(2).replace(',', '')
            final_balance_str = total_match.group(3).replace(',', '') # This might be the final balance on that line

            totals["total_withdrawal"] = float(total_withdraw_str)
            totals["total_deposit"] = float(total_deposit_str)
            totals["final_balance"] = float(final_balance_str) # Capture the last balance figure as 'final_balance'

        except Exception as e:
            print(f"Error parsing totals line: {e}")


    return {
        "account_info": account_info,
        "transactions": transactions,
        "totals": totals # Return the extracted totals
    }

@app.route("/parse-statement", methods=["POST"])
def upload_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if not file.filename.lower().endswith('.pdf'):
         return jsonify({"error": "Invalid file type, please upload a PDF"}), 400

    try:
        # Pass the file stream directly
        data = parse_bank_statement(file.stream)
        return jsonify(data)
    except Exception as e:
        # Log the detailed error and traceback
        print(f"Error in /parse-statement endpoint: {e}")
        print(traceback.format_exc())
        return jsonify({
            "error": f"An internal error occurred while processing the PDF: {e}",
            "traceback": traceback.format_exc() # Include traceback for debugging if needed (consider security implications in production)
        }), 500

if __name__ == "__main__":
    # Set host='0.0.0.0' to make it accessible on the network if needed
    app.run(debug=True, host='0.0.0.0', port=5000) # Example port