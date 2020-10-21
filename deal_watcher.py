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

deals = dict()


def main():
    r = redis.StrictRedis(
        host=settings['REDIS']['HOST'],
        port=settings['REDIS']['PORT'],
        db=settings['REDIS']['DB'],
        password=settings['REDIS']['PASSWORD']
    )
    p = r.pubsub()
    p.subscribe('new_deals')
    while True:
        update = p.get_message(ignore_subscribe_messages=True)
        if update:
            print('Got new deal update')
            print(update)
            deal_to_be_watched = json.loads(update['data'])
            deals[deal_to_be_watched['jid']] = deal_to_be_watched
            print('Current Deals to be watched set')
            print(deals)
        time.sleep(5)


def job_checker():
    sqlite_conn = sqlite3.connect('auditprotocol_1.db')
    sqlite_cursor = sqlite_conn.cursor()

    pow_client = PowerGateClient(fast_settings.config.powergate_url, False)
    while True:
        done_deal_jids = list()
        for deal_jid, deal in deals.items():
            j_stat = pow_client.ffs.get_storage_job(jid=deal['jid'], token=deal['token'])
            # print(j_stat.job)
            if j_stat.job.status == 5:  # 'JOB_STATUS_SUCCESS':
                print('Hurrah. Removing from deals to be watched...')
                done_deal_jids.append(deal_jid)
                # update status
                sqlite_cursor.execute("""
                    UPDATE accounting_records SET confirmed=1 WHERE cid=?            
                """, (deal['cid'], ))
                sqlite_cursor.connection.commit()
        for each_done_jid in done_deal_jids:
            del deals[each_done_jid]
        time.sleep(5)


if __name__ == '__main__':
    t1 = threading.Thread(target=main)
    t2 = threading.Thread(target=job_checker)
    t1.start()
    t2.start()
    t1.join()
    t2.join()