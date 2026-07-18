from flask import Flask, render_template, request, send_file
import io
from CDR14_main import (
    fetch_14column_cdr,
    fetch_msisdn_to_imei,
    fetch_imei_to_msisdn,
    fetch_lac_cell_cdr,
    fetch_cgi_cdr,
    fetch_foreign_cdr,
    fetch_retailer_cdr,
    expand_by_date
)

app = Flask(__name__)

latest_df = None
latest_filename = None


# ==================== HELPER: Filter by usage type ====================
def filter_dataframe(df, usage_filter):
    if usage_filter == "all" or df.empty:
        return df
    mapping = {
        "moc":         ["MOC"],
        "mtc":         ["MTC"],
        "moc&mtc":     ["MOC", "MTC"],
        "smsmo":       ["SMSMO"],
        "smsmt":       ["SMSMT"],
        "smsmo&smsmt": ["SMSMO", "SMSMT"],
    }
    return df[df["USAGETYPE"].isin(mapping.get(usage_filter, []))]


# ==================== HELPER: Build filename ====================
def make_filename(prefix, identifier, start_date, start_time, end_date, end_time):
    st = start_time.replace(":", "")
    et = end_time.replace(":", "")
    return f"{prefix}_{identifier}_{start_date}_{st}_{end_date}_{et}.csv"

def make_filenameNT(prefix, identifier, start_date, end_date):
    return f"{prefix}_{identifier}_{start_date}_{end_date}.csv"

# ==================== HELPER: Save + render table ====================
def render_result(df, prefix, identifier, start_date, start_time, end_date, end_time):
    global latest_df, latest_filename
    if df.empty:
        return "<p>No records found.</p>"
    latest_df = df
    latest_filename = make_filename(prefix, identifier, start_date, start_time, end_date, end_time)
    return df.to_html(index=False, classes="data-table")

def render_resultNT(df, prefix, identifier, start_date, end_date):
    global latest_df, latest_filename
    if df.empty:
        return "<p>No records found.</p>"
    latest_df = df
    latest_filename = make_filenameNT(prefix, identifier, start_date, end_date)
    return df.to_html(index=False, classes="data-table")

# ==================== 14 COLUMN CDR (A-Party) ====================
@app.route("/", methods=["GET", "POST"])
@app.route("/14_column_cdr", methods=["GET", "POST"])
def cdr_14col():
    table_html = None
    selected_filter = request.form.get("filter", "all")

    if request.method == "POST":
        msisdn     = request.form.get("MSISDN", "").strip()
        start_date = request.form.get("start_date", "")
        start_time = request.form.get("start_time", "00:00")
        end_date   = request.form.get("end_date", "")
        end_time   = request.form.get("end_time", "23:59")

        if not msisdn:
            table_html = "<p style='color:red'>Please enter MSISDN.</p>"
        else:
            try:
                df = fetch_14column_cdr([msisdn], start_date, end_date, start_time, end_time)
                df = filter_dataframe(df, selected_filter)
                table_html = render_result(df, "14COL", msisdn,
                                           start_date, start_time, end_date, end_time)
            except Exception as e:
                table_html = f"<p style='color:red'>Error: {e}</p>"

    return render_template("CDR14_14column.html",
                           table=table_html, selected_filter=selected_filter)


# ==================== CGI MSISDN CDR ====================
@app.route("/cgi_msisdn_cdr", methods=["GET", "POST"])
def cgi_msisdn_cdr():
    table_html = None
    selected_filter = request.form.get("filter", "all")

    if request.method == "POST":
        cgis = []
        single_cgi = request.form.get("CGI", "").strip()
        if single_cgi:
            cgis.append(single_cgi)

        batch_file = request.files.get("cgi_batch_file")
        if batch_file and batch_file.filename:
            content = batch_file.read().decode()
            cgis += [line.strip() for line in content.splitlines() if line.strip()]

        start_date = request.form.get("start_date", "")
        start_time = request.form.get("start_time", "00:00")
        end_date   = request.form.get("end_date", "")
        end_time   = request.form.get("end_time", "23:59")

        if not cgis:
            table_html = "<p style='color:red'>Please enter or upload a CGI.</p>"
        else:
            try:
                df = fetch_cgi_cdr(cgis, start_date, end_date, start_time, end_time)
                df = filter_dataframe(df, selected_filter)
                table_html = render_result(df, "CGI", cgis[0],
                                           start_date, start_time, end_date, end_time)
            except Exception as e:
                table_html = f"<p style='color:red'>Error: {e}</p>"

    return render_template("CDR14_CGI.html",
                           table=table_html, selected_filter=selected_filter)


# ==================== LAC CELL CDR ====================
@app.route("/lac_cell_cdr", methods=["GET", "POST"])
def lac_cell():
    table_html = None

    if request.method == "POST":
        lac        = request.form.get("LAC", "").strip()
        cell       = request.form.get("CELL", "").strip()
        start_date = request.form.get("start_date", "")
        start_time = request.form.get("start_time", "00:00")
        end_date   = request.form.get("end_date", "")
        end_time   = request.form.get("end_time", "23:59")

        if not all([lac, cell, start_date, end_date]):
            table_html = "<p style='color:red'>Please fill all fields.</p>"
        else:
            try:
                df = fetch_lac_cell_cdr(lac, cell, start_date, end_date, start_time, end_time)
                table_html = render_result(df, "LACCELL", f"{lac}_{cell}",
                                           start_date, start_time, end_date, end_time)
            except Exception as e:
                table_html = f"<p style='color:red'>Error: {e}</p>"

    return render_template("CDR14_lac_cell.html", table=table_html)


# ==================== FOREIGN NUMBER CDR (B-Party) ====================
@app.route("/foreign_number_cdr", methods=["GET", "POST"])
def foreign_number_cdr():
    table_html = None

    if request.method == "POST":
        msisdn     = request.form.get("MSISDN", "").strip()
        start_date = request.form.get("start_date", "")
        start_time = request.form.get("start_time", "00:00")
        end_date   = request.form.get("end_date", "")
        end_time   = request.form.get("end_time", "23:59")

        if not msisdn:
            table_html = "<p style='color:red'>Please enter MSISDN.</p>"
        else:
            try:
                df = fetch_foreign_cdr([msisdn], start_date, end_date, start_time, end_time)
                table_html = render_result(df, "FOREIGN", msisdn,
                                           start_date, start_time, end_date, end_time)
            except Exception as e:
                table_html = f"<p style='color:red'>Error: {e}</p>"

    return render_template("CDR14_foreign_number.html", table=table_html)


# ==================== RETAILER LOCATION ====================
@app.route("/retailer_location", methods=["GET", "POST"])
def retailer_location():
    table_html = None

    if request.method == "POST":
        msisdn     = request.form.get("MSISDN", "").strip()
        start_date = request.form.get("start_date", "")
        start_time = request.form.get("start_time", "00:00")
        end_date   = request.form.get("end_date", "")
        end_time   = request.form.get("end_time", "23:59")

        if not msisdn:
            table_html = "<p style='color:red'>Please enter MSISDN.</p>"
        else:
            try:
                # fetch_retailer_cdr single msisdn string নেয়, list না
                df = fetch_retailer_cdr(msisdn, start_date, end_date, start_time, end_time)
                table_html = render_result(df, "RETAILER", msisdn,
                                           start_date, start_time, end_date, end_time)
            except Exception as e:
                table_html = f"<p style='color:red'>Error: {e}</p>"

    return render_template("CDR14_retailer_location.html", table=table_html)


# # ==================== MSISDN <-> IMEI ====================

@app.route("/msisdn_to_imei", methods=["GET", "POST"])
def msisdn_to_imei():
    table_html = None

    if request.method == "POST":
        msisdn = request.form.get("MSISDN", "").strip()
        start_date = request.form.get("start")
        end_date = request.form.get("end")
    
        if not msisdn:
            table_html = "<p style='color:red'>Enter MSISDN</p>"
        else:
            try:
                df = fetch_msisdn_to_imei(msisdn)
                df = expand_by_date(df, start_date, end_date)
                table_html = render_resultNT(
                    df, "MSISDN_IMEI", msisdn,
                    start_date, end_date
                )
            except Exception as e:
                table_html = f"<p style='color:red'>Error: {e}</p>"
    return render_template("CDR14_msisdn_to_imei.html", table=table_html)

#----------------------------------------------------------------------------------------------

@app.route("/imei_to_msisdn", methods=["GET", "POST"])
def imei_to_msisdn():
    table_html = None

    if request.method == "POST":
        imei = request.form.get("IMEI", "").strip()
        start_date = request.form.get("start", "")
        end_date = request.form.get("end", "")

        if not imei:
            table_html = "<p style='color:red'>Enter IMEI</p>"
        else:
            try:
                df = fetch_imei_to_msisdn(imei)
                df = expand_by_date(df, start_date, end_date)
                table_html = render_resultNT(
                    df, "IMEI_MSISDN", imei,
                    start_date, end_date
                )
            except Exception as e:
                table_html = f"<p style='color:red'>Error: {e}</p>"
    return render_template("CDR14_imei_to_msisdn.html", table=table_html)

# ==================== DOWNLOAD CSV ====================
@app.route("/download_csv")
def download_csv():
    if latest_df is None:
        return "No data available", 400

    buf = io.StringIO()
    latest_df.to_csv(buf, index=False)
    buf.seek(0)

    return send_file(
        io.BytesIO(buf.getvalue().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name=latest_filename or "cdr_data.csv",
    )


# ==================== RUN ====================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10001, debug=True)