from pygate_grpc.client import PowerGateClient
from pygate_grpc.ffs import get_file_bytes, bytes_to_chunks, chunks_to_bytes
from google.protobuf.json_format import MessageToDict
from pygate_grpc.ffs import bytes_to_chunks
import redis
import json
import time
import threading
import fast_settings
import queue
import sqlite3

with open('settings.json') as f:
    settings = json.load(f)


def main():
    sqlite_conn = sqlite3.connect('auditprotocol_1.db')
    sqlite_cursor = sqlite_conn.cursor()
    r = redis.StrictRedis(
        host=settings['REDIS']['HOST'],
        port=settings['REDIS']['PORT'],
        db=settings['REDIS']['DB'],
        password=settings['REDIS']['PASSWORD']
    )
    pow_client = PowerGateClient(fast_settings.config.powergate_url, False)
    while True:
        retr_req = r.brpop('retrieval_requests')
        retrieval_request = json.loads(retr_req[1])
        print(retrieval_request)
        local_cid = retrieval_request['localCID']
        request_id = retrieval_request['requestId']
        s = sqlite_cursor.execute("""
            SELECT cid, token FROM accounting_records WHERE localCID=?
        """, (local_cid, ))
        res = s.fetchone()
        ffs_cid = res[0]
        token = res[1]
        print("Retrieving file " + ffs_cid + " from FFS.")
        file_ = pow_client.ffs.get(ffs_cid, token)
        file_name = f'{request_id}'
        print('Saving to ', file_name)
        with open(file_name, 'wb') as f:
            for _ in file_:
                f.write(_)
        sqlite_cursor.execute("""
            UPDATE retrievals SET retrievedFile=?, completed=1 WHERE requestID=?
        """, (file_name, request_id))
        sqlite_conn.commit()

if __name__ == '__main__':
    main()