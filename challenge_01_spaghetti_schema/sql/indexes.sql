-- ============================================================================
--  Challenge 01 — indexes.sql
--  Query-path/join optimization for the analytics questions in the challenge:
--    * weekly sales by department
--    * promo lift
--    * member vs non-member mix
--    * daily store-sales forecasting
-- ============================================================================

-- ---- time-series / forecast access: "sales by day, per store" ---------------
CREATE INDEX idx_receipts_store_datetime ON receipts (store_id, sale_datetime);
CREATE INDEX idx_receipts_datetime        ON receipts (sale_datetime);

-- ---- segment / tender filters -------------------------------------------------
CREATE INDEX idx_receipts_segment ON receipts (customer_segment);

-- ---- joining line items back to their parent & to products/promotions -------
CREATE INDEX idx_line_items_receipt  ON line_items (receipt_id);
CREATE INDEX idx_line_items_product  ON line_items (product_upc);
-- promo_id is NULL for ~90% of lines; partial index keeps it small & fast
CREATE INDEX idx_line_items_promo    ON line_items (promo_id)
    WHERE promo_id IS NOT NULL;

-- ---- promo lookups -----------------------------------------------------------
CREATE INDEX idx_promotions_product ON promotions (product_upc);
CREATE INDEX idx_promotions_dates   ON promotions (start_date, end_date);

-- ---- inventory roll-ups ------------------------------------------------------
CREATE INDEX idx_inventory_store_product ON inventory_snapshots (store_id, product_upc);
CREATE INDEX idx_inventory_date          ON inventory_snapshots (snapshot_date);

-- ---- dimension drill-down (department -> category -> product) ----------------
CREATE INDEX idx_products_category  ON products (category_id);
CREATE INDEX idx_products_brand     ON products (brand_id);

-- Optional: support "top-N by revenue" scans and analytics ordering.
CREATE INDEX idx_line_items_subtotal ON line_items (line_subtotal);