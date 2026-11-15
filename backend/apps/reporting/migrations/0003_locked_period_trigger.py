from django.db import migrations

# Defence in depth (P7.5): even if application code forgot a check, the database refuses any change
# to accomplishments or supporting files of a locked month. SECURITY DEFINER so the period lookup is
# not affected by row-level security; the error message is stable for the API layer.
TABLES = ("activity_actual", "indicator_actual", "attachment")

CREATE = """
CREATE OR REPLACE FUNCTION reject_change_in_locked_period() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    target_period uuid;
BEGIN
    IF TG_OP = 'DELETE' THEN
        target_period := OLD.period_id;
    ELSE
        target_period := NEW.period_id;
    END IF;
    IF EXISTS (SELECT 1 FROM reporting_period WHERE id = target_period AND status = 'locked')
       OR (TG_OP = 'UPDATE' AND EXISTS (
            SELECT 1 FROM reporting_period WHERE id = OLD.period_id AND status = 'locked')) THEN
        RAISE EXCEPTION 'period is locked: % on % refused', TG_OP, TG_TABLE_NAME
            USING ERRCODE = 'check_violation';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION reject_change_in_locked_period() FROM PUBLIC;
""" + "".join(
    f"""
DROP TRIGGER IF EXISTS {t}_locked_period ON {t};
CREATE TRIGGER {t}_locked_period BEFORE INSERT OR UPDATE OR DELETE ON {t}
    FOR EACH ROW EXECUTE FUNCTION reject_change_in_locked_period();
"""
    for t in TABLES
)

DROP = "".join(f"DROP TRIGGER IF EXISTS {t}_locked_period ON {t};\n" for t in TABLES) + (
    "DROP FUNCTION IF EXISTS reject_change_in_locked_period();"
)


class Migration(migrations.Migration):
    dependencies = [("reporting", "0002_rls")]

    operations = [migrations.RunSQL(CREATE, DROP)]
