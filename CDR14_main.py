import oracledb
import pandas as pd

# ==================== ORACLE CONNECTIONS ====================
def get_connection():
    return oracledb.connect(
        user="dwh_user03",
        password="dwh_user_123",
        dsn="192.168.61.204/dwhdb03"
    )

def imei_connection():
    return oracledb.connect(
        user="dwh_user",
        password="dwh_user_123",
        dsn="192.168.61.16:1521/datadb01"
    )

# ==================== BASE SQL (14-col) ====================
BASE_SQL = """
SELECT /*+ PARALLEL(M, 16) PARALLEL(Z, 16) */
       TO_CHAR(TO_DATE(M.M07_ANSWERTIMESTAMP, 'YYYYMMDDHH24MISS'), 'DD/MM/YYYY HH24:MI:SS') AS START_TIME,
       'TELETALK'                                                 AS PROVIDERNAME,
       M.M04_MSISDNAPARTY                                         AS APARTY,
       CASE
         WHEN SUBSTR(M05_MSISDNBPARTY,1,3)='880'
           THEN '880' || SUBSTR(M05_MSISDNBPARTY,-10)
         WHEN LENGTH(M05_MSISDNBPARTY)=10
           THEN '880' || M05_MSISDNBPARTY
         ELSE M05_MSISDNBPARTY
       END                                                        AS BPARTY,
       M.M08_CALLDUR                                              AS CALLDURATION,
       M.M01_CALLTYPE                                             AS USAGETYPE,
       Z.TECHNOLOGY                                               AS NETWORKTYPE,
       '470'                                                      AS MCCSTARTA,
       '04'                                                       AS MNCSTARTA,
       Z.LAC                                                      AS LACSTARTA,
       M.M09_LOCATION                                             AS CISTARTA,
       M.M03_IMEI                                                 AS IMEI,
       M.M02_IMSI                                                 AS IMSIA,
       Z.FULL_ADDRESS                                             AS ADDRESS
  FROM L1_MSC M
  JOIN ZONE_DIM Z ON M.M09_LOCATION = Z.CGI
 WHERE M.M07_ANSWERTIMESTAMP >= REPLACE(:start_date,'-','') || REPLACE(:start_time,':','') || '00'
   AND M.M07_ANSWERTIMESTAMP <= REPLACE(:end_date,'-','')   || REPLACE(:end_time,':','')   || '59'
   AND M.PROCESSED_DATE BETWEEN TO_DATE(:start_date,'YYYY-MM-DD') - 1
                             AND TO_DATE(:end_date,'YYYY-MM-DD')   + 1
   AND {filter_col} IN ({placeholders})
 ORDER BY M.M07_ANSWERTIMESTAMP DESC
"""

# ==================== INTERNAL RUNNER ====================

def _run_query(values, start_date, end_date, filter_col, start_time="00:00", end_time="23:59"):
    if isinstance(values, str):
        values = [values]
    if not values:
        raise ValueError("No values provided")

    placeholders = ", ".join([f":val{i}" for i in range(len(values))])
    sql = BASE_SQL.format(filter_col=filter_col, placeholders=placeholders)
  
    binds = {
        "start_date": start_date, 
        "end_date": end_date,
        "start_time": start_time,
        "end_time": end_time
    }
    
    for i, v in enumerate(values):
        binds[f"val{i}"] = v

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, binds)
        cols = [c[0] for c in cur.description]
        rows = cur.fetchall()
        return pd.DataFrame(rows, columns=cols)
    finally:
        cur.close()
        conn.close()


# ==================== PUBLIC FUNCTIONS ====================

def fetch_14column_cdr(msisdns, start_date, end_date, start_time="00:00", end_time="23:59"):
    return _run_query(msisdns, start_date, end_date, 
                      filter_col="M.M04_MSISDNAPARTY", 
                      start_time=start_time, end_time=end_time)

def fetch_cgi_cdr(cgis, start_date, end_date, start_time="00:00", end_time="23:59"):
    return _run_query(cgis, start_date, end_date, 
                      filter_col="M.M09_LOCATION", 
                      start_time=start_time, end_time=end_time)


def fetch_foreign_cdr(msisdns, start_date, end_date, start_time="00:00", end_time="23:59"):
    return _run_query(msisdns, start_date, end_date, 
                      filter_col="M.M05_MSISDNBPARTY", 
                      start_time=start_time, end_time=end_time)


def fetch_lac_cell_cdr(lac, cell, start_date, end_date, start_time="00:00", end_time="23:59"):
    cgi = f"47004{str(lac).strip().zfill(5)}{str(cell).strip().zfill(5)}"
    return fetch_cgi_cdr([cgi], start_date, end_date, start_time, end_time)


# ==================== RETAILER LOCATION (alag SQL) ====================
def fetch_retailer_cdr(msisdn, start_date, end_date, start_time="00:00", end_time="23:59"):
    """
    Retailer location — Fixed DPY-4010 & Time Filter Issues
    """
    SQL = """
    SELECT /*+ PARALLEL(M, 16) PARALLEL(Z, 16) */
           TO_CHAR(TO_DATE(M.M07_ANSWERTIMESTAMP, 'YYYYMMDDHH24MISS'), 'DD/MM/YYYY HH24:MI:SS') AS "Date",
           M.M04_MSISDNAPARTY                                       AS "Retailer Number",
           Z.SITE_ID                                                AS "SITE_ID",
           Z.SITE_NAME                                              AS "SITE_NAME",
           Z.FULL_ADDRESS                                           AS "Address"
      FROM L1_MSC M
      JOIN ZONE_DIM Z ON M.M09_LOCATION = Z.CGI
     WHERE M.M04_MSISDNAPARTY = :msisdn
       AND M.M07_ANSWERTIMESTAMP >= REPLACE(:start_date,'-','') || REPLACE(:start_time,':','') || '00'
       AND M.M07_ANSWERTIMESTAMP <= REPLACE(:end_date,'-','')   || REPLACE(:end_time,':','')   || '59'
       AND M.PROCESSED_DATE BETWEEN TO_DATE(:start_date, 'YYYY-MM-DD') - 1
                                AND TO_DATE(:end_date,   'YYYY-MM-DD') + 1
     ORDER BY M.M07_ANSWERTIMESTAMP DESC
    """
    
    binds = {
        "msisdn":     msisdn,
        "start_date": start_date,
        "end_date":   end_date,
        "start_time": start_time, 
        "end_time":   end_time    
    }

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(SQL, binds)
        cols = [c[0] for c in cur.description]
        rows = cur.fetchall()
        return pd.DataFrame(rows, columns=cols)
    except Exception as e:
        print(f"Error: {e}")
        return pd.DataFrame()
    finally:
        cur.close()
        conn.close()

# ========================= MSISDN <--> IMEI ==============================

def fetch_msisdn_to_imei(msisdn):

    TAB_SQL = """
    SELECT MSISDN, IMEI, IMSI
    FROM IMEI_TRIPLET
    WHERE MSISDN = :msisdn
    """

    binds = {
        "msisdn": msisdn
    }

    conn = imei_connection()
    try:
        cur = conn.cursor()
        cur.execute(TAB_SQL, binds)
        cols = [c[0] for c in cur.description]
        rows = cur.fetchall()
        return pd.DataFrame(rows, columns=cols)
    finally:
        cur.close()
        conn.close()

#-------------------------------------------------------------------------------------------

def fetch_imei_to_msisdn(imei):
    TAB_SQL = """
    SELECT MSISDN, IMEI, IMSI
    FROM IMEI_TRIPLET
    WHERE IMEI = :IMEI
    """

    binds = {
        "imei":     imei
    }

    conn = imei_connection()
    try:
        cur = conn.cursor()
        cur.execute(TAB_SQL, binds)
        cols = [c[0] for c in cur.description]
        rows = cur.fetchall()
        return pd.DataFrame(rows, columns=cols)
    except Exception as e:
        print(f"Error: {e}")
        return pd.DataFrame()
    finally:
        cur.close()
        conn.close()

#================================== Date Fromatting =======================================

def clean_date(value):
    if not value or str(value).strip() == "":
        return None
    try:
        return pd.to_datetime(value)
    except Exception:
        return None

def safe_date_range(start_date, end_date):
    if not start_date or not end_date:
        raise ValueError("Start and end date are required")

    start = pd.to_datetime(start_date, errors='coerce')
    end = pd.to_datetime(end_date, errors='coerce')

    if pd.isna(start) or pd.isna(end):
        raise ValueError("Invalid date format")

    return pd.date_range(start=start, end=end)

def expand_by_date(df, start_date, end_date):
    if df.empty:
        return df

    date_range = safe_date_range(start_date, end_date)[::-1]

    expanded_rows = []

    for _, row in df.iterrows():
        for d in date_range:
            expanded_rows.append({
                "DATE_VALUE": d.strftime("%d/%m/%Y"),
                "MSISDN": row["MSISDN"],
                "IMEI": row["IMEI"],
                "IMSI": row["IMSI"]
            })

    return pd.DataFrame(expanded_rows)