import oracledb
conn = oracledb.connect(
    user="dwh_user03",
    password="dwh_user_123",
    dsn="192.168.61.204/dwhdb03"
)
print("Connected")
conn.close()

conn2 = oracledb.connect(
        user="dwh_user",
        password="dwh_user_123",
        dsn="192.168.61.16:1521/datadb01"
    )
print('Connected - 2')
conn2.close()