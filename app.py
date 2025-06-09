from flask import Flask, send_file, request
from db import authenticate
from admin import export_pdf

app = Flask(__name__)

@app.route("/export", methods=["POST"])
def download_report():
    pin = request.form.get("pin", "")
    auth = authenticate(pin)
    if not auth or not auth[2]:
        return "Unauthorized", 403
    export_pdf("latest_report.pdf")
    return send_file("latest_report.pdf", as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=False)