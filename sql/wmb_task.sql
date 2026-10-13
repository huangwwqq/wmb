-- 外贸邦生产者总表 / 公司任务表
-- update_time 由触发器维护，写入方不要传这个字段

CREATE OR REPLACE FUNCTION public.wmb_touch_update_time()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.update_time := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

CREATE TABLE IF NOT EXISTS public.wmb_task (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    country character varying(2) NOT NULL,
    type integer NOT NULL,
    number integer NOT NULL DEFAULT 0,
    flag integer NOT NULL DEFAULT 0,
    update_time timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE public.wmb_task IS '外贸邦国家任务。type 1采购商 2供应商；flag 0未完成 1已完成';
COMMENT ON COLUMN public.wmb_task.country IS '国家二字码';
COMMENT ON COLUMN public.wmb_task.number IS '该国家该类型公司数量（含邮箱）';

CREATE UNIQUE INDEX IF NOT EXISTS ux_wmb_task_country_type ON public.wmb_task (country, type);
CREATE INDEX IF NOT EXISTS ix_wmb_task_country ON public.wmb_task (country);
CREATE INDEX IF NOT EXISTS ix_wmb_task_flag ON public.wmb_task (flag);
CREATE INDEX IF NOT EXISTS ix_wmb_task_update_time ON public.wmb_task (update_time);

DROP TRIGGER IF EXISTS trg_wmb_task_update_time ON public.wmb_task;
CREATE TRIGGER trg_wmb_task_update_time
    BEFORE INSERT OR UPDATE ON public.wmb_task
    FOR EACH ROW EXECUTE FUNCTION public.wmb_touch_update_time();

CREATE TABLE IF NOT EXISTS public.wmb_company_task (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id text NOT NULL,
    type integer NOT NULL,
    flag integer NOT NULL DEFAULT 0,
    update_time timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE public.wmb_company_task IS '外贸邦公司任务。type 1采购商 2供应商；flag 0未完成 1已完成';
COMMENT ON COLUMN public.wmb_company_task.company_id IS '源站公司 ID';

CREATE UNIQUE INDEX IF NOT EXISTS ux_wmb_company_task_company_id ON public.wmb_company_task (company_id);
CREATE INDEX IF NOT EXISTS ix_wmb_company_task_type ON public.wmb_company_task (type);
CREATE INDEX IF NOT EXISTS ix_wmb_company_task_flag ON public.wmb_company_task (flag);
CREATE INDEX IF NOT EXISTS ix_wmb_company_task_update_time ON public.wmb_company_task (update_time);

DROP TRIGGER IF EXISTS trg_wmb_company_task_update_time ON public.wmb_company_task;
CREATE TRIGGER trg_wmb_company_task_update_time
    BEFORE INSERT OR UPDATE ON public.wmb_company_task
    FOR EACH ROW EXECUTE FUNCTION public.wmb_touch_update_time();
