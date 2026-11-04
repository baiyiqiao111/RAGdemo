from sqlalchemy import BigInteger, Integer

# SQLite 下 BigInteger 自增主键不生效，用 variant 兼容
PK = BigInteger().with_variant(Integer, "sqlite")
