# Audit Protocol

## [Write up](./AuditProtocol-EthOnline2020.pdf)

## [Demo](https://www.youtube.com/watch?v=yKn1JPr8G7o)


## Backend

### Setup

1. `pip install -r requirements.txt`
2. `python db_setup.py`
3. Setup account and deploy [contract](./AuditRecordStore.sol) on [MaticVigil](https://maticvigil.com/docs/)
4. Setup redis.
5. Clone [`settings.example.json`](./settings.example.json) to `settings.json` and [`fast_setting.example.py`](./fast_settings.example.py) to `fast_settings.py` with your values.
6. Bring up [Powergate](https://github.com/textileio/powergate) Docker with [localnet](https://github.com/textileio/powergate/#localnet-mode): `make localnet`

### Scripts to Run

1. `uvicorn main:app --port 9000`
2. `python retrieval_worker.py`
3. `python deal_watcher.py`

## [>> Setting up Frontend](./frontend/README.md)
