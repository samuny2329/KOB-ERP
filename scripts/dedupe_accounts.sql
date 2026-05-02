-- Deduplicate account_account: keep the row with smallest id per code,
-- repoint all FK references to it, delete the rest.

CREATE TEMP TABLE acc_dups AS
SELECT
    (code_store->>'1') AS code,
    MIN(id)          AS keep_id,
    array_agg(id ORDER BY id) AS all_ids
FROM account_account
WHERE code_store->>'1' IS NOT NULL
GROUP BY code_store->>'1'
HAVING COUNT(*) > 1;

-- Build (old_id → keep_id) mapping
CREATE TEMP TABLE acc_remap AS
SELECT unnest(all_ids[2:array_length(all_ids,1)]) AS old_id, keep_id
FROM acc_dups;

SELECT 'duplicate codes' AS m, COUNT(*) FROM acc_dups;
SELECT 'rows to delete' AS m, COUNT(*) FROM acc_remap;

-- Repoint key FK columns (the most common ones touched by daily ops).
UPDATE account_move_line aml
SET account_id = r.keep_id
FROM acc_remap r WHERE aml.account_id = r.old_id;

UPDATE account_tax_repartition_line atrl
SET account_id = r.keep_id
FROM acc_remap r WHERE atrl.account_id = r.old_id;

UPDATE account_journal aj
SET default_account_id = r.keep_id
FROM acc_remap r WHERE aj.default_account_id = r.old_id;

UPDATE account_journal aj
SET suspense_account_id = r.keep_id
FROM acc_remap r WHERE aj.suspense_account_id = r.old_id;

-- Repoint reconcile model lines, payment terms, etc. — fail soft if missing
DO $$
BEGIN
  BEGIN
    UPDATE account_reconcile_model_line arml
    SET account_id = r.keep_id
    FROM acc_remap r WHERE arml.account_id = r.old_id;
  EXCEPTION WHEN OTHERS THEN NULL;
  END;
END $$;

-- Now safe to delete duplicate accounts
DELETE FROM account_account
WHERE id IN (SELECT old_id FROM acc_remap);

SELECT 'remaining duplicate codes' AS m, COUNT(*) FROM (
  SELECT code_store->>'1' AS code FROM account_account
  WHERE code_store->>'1' IS NOT NULL
  GROUP BY 1 HAVING COUNT(*) > 1
) t;

SELECT 'total accounts now' AS m, COUNT(*) FROM account_account;
