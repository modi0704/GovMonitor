"""Closed months stay unchangeable, with one exception: deleting an office (Settings → Offices →
Delete) removes its reports and files from closed months too. The deletion sets the transaction-
local ``app.office_delete`` before removing rows; only DELETE is let through, never INSERT or UPDATE.
"""

from django.db import migrations

FUNCTION = """
CREATE OR REPLACE FUNCTION reject_change_in_locked_period() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    target_period uuid;
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF current_setting('app.office_delete', true) = 'on' THEN
            RETURN OLD;  -- an office and everything recorded for it is being deleted
        END IF;
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
"""

PREVIOUS = """
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
"""


class Migration(migrations.Migration):
    dependencies = [("reporting", "0003_locked_period_trigger")]

    operations = [migrations.RunSQL(FUNCTION, PREVIOUS)]
