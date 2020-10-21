from typing import Optional, Union
from fastapi import Depends, FastAPI, WebSocket, HTTPException, status, Security, Request, Response, BackgroundTasks, Cookie, Query, WebSocketDisconnect
from fastapi.security.api_key import APIKeyQuery, APIKeyHeader, APIKey
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse, JSONResponse
from pygate_grpc.client import PowerGateClient
from pygate_grpc.ffs import get_file_bytes, bytes_to_chunks, chunks_to_bytes
from google.protobuf.json_format import MessageToDict
from pygate_grpc.ffs import bytes_to_chunks
from eth_utils import keccak
from io import BytesIO
from maticvigil.EVCore import EVCore
from uuid import uuid4
import sqlite3
import fast_settings
import logging
import sys
import json
import aioredis

formatter = logging.Formatter(u"%(levelname)-8s %(name)-4s %(asctime)s,%(msecs)d %(module)s-%(funcName)s: %(message)s")

stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.DEBUG)
# stdout_handler.setFormatter(formatter)

stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setLevel(logging.ERROR)
# stderr_handler.setFormatter(formatter)
rest_logger = logging.getLogger(__name__)
rest_logger.setLevel(logging.DEBUG)
rest_logger.addHandler(stdout_handler)
rest_logger.addHandler(stderr_handler)

# setup CORS origins stuff
origins = ["*"]

app = FastAPI(docs_url=None, openapi_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

evc = EVCore(verbose=True)
contract = evc.generate_contract_sdk(
    contract_address='0x5a07f5bdc9f82096948c53aee6fc19c4769ffb9d',
    app_name='auditrecords'
)

with open('settings.json') as f:
    settings = json.load(f)

REDIS_CONN_CONF = {
    "host": settings['REDIS']['HOST'],
    "port": settings['REDIS']['PORT'],
    "password": settings['REDIS']['PASSWORD'],
    "db": settings['REDIS']['DB']
}
#
STORAGE_CONFIG = {
  "hot": {
    "enabled": True,
    "allowUnfreeze": True,
    "ipfs": {
      "addTimeout": 30
    }
  },
  "cold": {
    "enabled": True,
    "filecoin": {
      "repFactor": 1,
      "dealMinDuration": 518400,
      "renew": {
      },
      "addr": "t3vwiyojfhcvrdijdgh3egk5vpajg5427uogfhzvtpbaf4a5sn2drahw5bfdk4pd4vg6baxxn3y4mtb7n6ll2q"
    }
  }
}


@app.on_event('startup')
async def startup_boilerplate():
    app.redis_pool: aioredis.Redis = await aioredis.create_redis_pool(
        address=(REDIS_CONN_CONF['host'], REDIS_CONN_CONF['port']),
        db=REDIS_CONN_CONF['db'],
        password=REDIS_CONN_CONF['password'],
        maxsize=5
    )
    app.sqlite_conn = sqlite3.connect('auditprotocol_1.db')
    app.sqlite_cursor = app.sqlite_conn.cursor()


async def load_user_from_auth(
        request: Request = None
) -> Union[str, None]:
    api_key_in_header = request.headers['Auth-Token'] if 'Auth-Token' in request.headers else None
    if not api_key_in_header:
        return None
    rest_logger.debug(api_key_in_header)
    ffs_token_c = request.app.sqlite_cursor.execute("""
        SELECT token FROM api_keys WHERE apiKey=?
    """, (api_key_in_header, ))
    ffs_token = ffs_token_c.fetchone()
    # rest_logger.debug(ffs_token)
    if ffs_token:
        ffs_token = ffs_token[0]
    return ffs_token


@app.post('/create')
async def create_filecoin_filesystem(
        request: Request
):
    req_json = await request.json()
    hot_enabled = req_json.get('hotEnabled', True)
    pow_client = PowerGateClient(fast_settings.config.powergate_url, False)
    new_ffs = pow_client.ffs.create()
    rest_logger.info('Created new FFS')
    rest_logger.info(new_ffs)
    if not hot_enabled:
        default_config = pow_client.ffs.default_config(new_ffs.token)
        rest_logger.debug(default_config)
        new_storage_config = STORAGE_CONFIG
        new_storage_config['cold']['filecoin']['addr'] = default_config.default_storage_config.cold.filecoin.addr
        new_storage_config['hot']['enabled'] = False
        pow_client.ffs.set_default_config(json.dumps(new_storage_config), new_ffs.token)
        rest_logger.debug('Set hot storage to False')
        rest_logger.debug(new_storage_config)
    # rest_logger.debug(type(default_config))
    api_key = str(uuid4())
    request.app.sqlite_cursor.execute("""
        INSERT INTO api_keys VALUES (?, ?)
    """, (new_ffs.token, api_key))
    request.app.sqlite_cursor.connection.commit()
    return {'apiKey': api_key}


@app.get('/payload/{recordCid:str}')
async def record(request: Request, response:Response, recordCid: str):
    # record_chain = contract.getTokenRecordLogs('0x'+keccak(text=tokenId).hex())
    c = request.app.sqlite_cursor.execute('''
        SELECT confirmed FROM accounting_records WHERE localCID=?
    ''', (recordCid, ))
    res = c.fetchone()[0]
    if res == 0:
        # response.status_code = status.HTTP_404_NOT_FOUND
        return {'requestId': None, 'error': 'NotPinnedYet'}
    request_id = str(uuid4())
    await request.app.redis_pool.lpush('retrieval_requests', json.dumps({'localCID': recordCid, 'requestId': request_id}))
    request.app.sqlite_cursor.execute("""
        INSERT INTO retrievals VALUES (?, "", 0)
    """, (request_id, ))
    request.app.sqlite_cursor.connection.commit()
    return {'requestId': request_id}


@app.get('/requests/{requestId:str}')
async def request_status(request: Request, requestId: str):
    c = request.app.sqlite_cursor.execute('''
        SELECT * FROM retrievals WHERE requestID=?
    ''', (requestId, ))
    res = c.fetchone()
    return {'requestID': requestId, 'completed': bool(res[2])}


@app.post('/')
# @app.post('/jsonrpc/v1/{appID:str}')
async def root(
        request: Request,
        response: Response,
        bg_task: BackgroundTasks,
        # app_id: Optional[str] = None,
        api_key_extraction=Depends(load_user_from_auth)
):
    if not api_key_extraction:
        response.status_code = status.HTTP_403_FORBIDDEN
        return {'error': 'Forbidden'}
    pow_client = PowerGateClient(fast_settings.config.powergate_url, False)
    # if request.method == 'POST':
    req_args = await request.json()
    payload = req_args['payload']
    token = api_key_extraction
    payload_bytes = BytesIO(json.dumps(payload).encode('utf-8'))
    payload_iter = bytes_to_chunks(payload_bytes)
    # adds to hot tier, IPFS
    stage_res = pow_client.ffs.stage(payload_iter, token=token)
    rest_logger.debug('Staging level results:')
    rest_logger.debug(stage_res)
    # uploads to filecoin
    push_res = pow_client.ffs.push(stage_res.cid, token=token)
    rest_logger.debug('Cold tier finalization results:')
    rest_logger.debug(push_res)
    await request.app.redis_pool.publish_json('new_deals', {'cid': stage_res.cid, 'jid': push_res.job_id, 'token': token})
    # storage_deals = pow_client.ffs.list_storage_deal_records(
    #     include_pending=True, include_final=True, token=token
    # )
    #
    # rest_logger.debug("Storage deals: ")
    # for record in storage_deals.records:
    #     rest_logger.debug(record)
    #
    # retrieval_deals = client.ffs.list_retrieval_deal_records(
    #     include_pending=True, include_final=True, token=ffs.token
    # )
    # print("Retrieval deals: ")
    # for record in retrieval_deals.records:
    #     print(record)
    #
    # check = pow_client.ffs.info(stage_res.cid, token)
    # rest_logger.debug('Pinning status:')
    # rest_logger.debug(check)
    payload_hash = '0x' + keccak(text=json.dumps(payload)).hex()
    token_hash = '0x' + keccak(text=token).hex()
    tx_hash_obj = contract.commitRecordHash(**dict(
        payloadHash=payload_hash,
        tokenHash=token_hash
    ))
    tx_hash = tx_hash_obj[0]['txHash']
    rest_logger.debug('Committed record append to contract..')
    rest_logger.debug(tx_hash_obj)
    local_id = str(uuid4())
    request.app.sqlite_cursor.execute('INSERT INTO accounting_records VALUES '
                                      '(?, ?, ?, ?, ?)',
                                      (token, stage_res.cid, local_id, tx_hash, 0))
    request.app.sqlite_cursor.connection.commit()
    return {'commitTx': tx_hash, 'recordCid': local_id}
    # if request.method == 'GET':
    #     healthcheck = pow_client.health.check()
    #     rest_logger.debug('Health check:')
    #     rest_logger.debug(healthcheck)
    #     return {'status': healthcheck}
