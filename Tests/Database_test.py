import oracledb

conn = oracledb.connect(user="dwh_user03", password="dwh_user_123", dsn="192.168.61.204/dwhdb03")
cur = conn.cursor()
cur.execute("SELECT * FROM L1_MSC WHERE ROWNUM <= 5")
print(cur.fetchall())
cur.close()
conn.close()