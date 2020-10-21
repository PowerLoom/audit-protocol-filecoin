import sqlite3

sqlite_conn = sqlite3.connect('auditprotocol_1.db')
sqlite_cursor = sqlite_conn.cursor()

try:
    sqlite_cursor.execute('''CREATE TABLE api_keys 
    (
        token text, 
        apiKey text
    )
''')
except sqlite3.OperationalError:
    pass


try:
    sqlite_cursor.execute('''CREATE TABLE accounting_records 
    (
        token text, 
        cid text, 
        localCID text, 
        txHash text, 
        confirmed integer
    )
''')
except sqlite3.OperationalError:
    pass


try:
    sqlite_cursor.execute('''CREATE TABLE retrievals 
    (
        requestID text, 
        retrievedFile text, 
        completed integer
    )
''')
except sqlite3.OperationalError:
    pass
