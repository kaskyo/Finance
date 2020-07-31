DROP TABLE history;
DROP TABLE users;
DROP TABLE user_stock;
DROP TABLE stocks;




CREATE TABLE history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    stock_id INTEGER NOT NULL,
    transaction_sum FLOAT,
    current_price FLOAT,
    stocks_number INTEGER NOT NULL,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE users(
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    hash TEXT NOT NULL,
    balance FLOAT
);

CREATE TABLE user_stock (
    user_id INTEGER NOT NULL,
    stock_id INTEGER NOT NULL,
    number INTEGER NOT NULL
);

CREATE TABLE stocks (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    symbol TEXT,
    price FLOAT,
    trend FLOAT
);