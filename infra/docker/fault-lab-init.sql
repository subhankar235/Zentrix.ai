CREATE TABLE IF NOT EXISTS fault_lab_orders (
    id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT NOT NULL,
    amount NUMERIC NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO fault_lab_orders (customer_id, amount)
SELECT (g % 1000) + 1, (g % 100) + 1
FROM generate_series(1, 100000) AS g;

CREATE INDEX fault_lab_orders_customer_id_idx ON fault_lab_orders (customer_id);
ANALYZE fault_lab_orders;
