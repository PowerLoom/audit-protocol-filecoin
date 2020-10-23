# Audit Protocol

[Write up](./AuditProtocol-EthOnline2020.pdf)

[Demo](https://youtube.com/)


## Setting up Backend

### Setup

1. `pip install -r requirements.txt`
2. python db_setup.py
3. Setup account and deploy Contract on [MaticVigil](https://maticvigil.com/docs/)
4. Setup redis.
5. Clone settings and fast_settings with your values.
6. Bring up [Powergate](https://github.com/textileio/powergate) Docker with localnet.

### Scripts to Run

1. `uvicorn main:app --port 9000`
2. `python retrieval_worker.py`
3. `python deal_watcher.py`

## [Setting up Frontend](./frontend/README.md)
