from pydantic import BaseSettings


class Config(BaseSettings):
    powergate_url: str = '192.168.99.100:5002'

config = Config()

