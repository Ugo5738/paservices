

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;


COMMENT ON SCHEMA "public" IS 'standard public schema';



CREATE EXTENSION IF NOT EXISTS "pg_graphql" WITH SCHEMA "graphql";






CREATE EXTENSION IF NOT EXISTS "pg_stat_statements" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgcrypto" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "supabase_vault" WITH SCHEMA "vault";






CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA "extensions";






CREATE OR REPLACE FUNCTION "public"."log_super_id_changes"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        INSERT INTO super_id_audit_logs (super_id, action, performed_by, details)
        VALUES (
            NEW.id,
            'UPDATE',
            NEW.created_by,
            jsonb_build_object(
                'old_value', row_to_json(OLD)::jsonb,
                'new_value', row_to_json(NEW)::jsonb
            )
        );
    ELSIF (TG_OP = 'DELETE') THEN
        INSERT INTO super_id_audit_logs (super_id, action, performed_by, details)
        VALUES (
            OLD.id,
            'DELETE',
            OLD.created_by,
            jsonb_build_object('old_value', row_to_json(OLD)::jsonb)
        );
    END IF;
    
    RETURN NULL; -- result is ignored since this is an AFTER trigger
END;
$$;


ALTER FUNCTION "public"."log_super_id_changes"() OWNER TO "postgres";

SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "public"."alembic_version" (
    "version_num" character varying(32) NOT NULL
);


ALTER TABLE "public"."alembic_version" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."generated_super_ids" (
    "id" bigint NOT NULL,
    "super_id" "uuid" NOT NULL,
    "generated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "requested_by_client_id" character varying,
    "super_id_metadata" "jsonb"
);


ALTER TABLE "public"."generated_super_ids" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."generated_super_ids_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."generated_super_ids_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."generated_super_ids_id_seq" OWNED BY "public"."generated_super_ids"."id";



ALTER TABLE ONLY "public"."generated_super_ids" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."generated_super_ids_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."alembic_version"
    ADD CONSTRAINT "alembic_version_pkc" PRIMARY KEY ("version_num");



ALTER TABLE ONLY "public"."generated_super_ids"
    ADD CONSTRAINT "generated_super_ids_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."generated_super_ids"
    ADD CONSTRAINT "generated_super_ids_super_id_key" UNIQUE ("super_id");





ALTER PUBLICATION "supabase_realtime" OWNER TO "postgres";


GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";

























































































































































GRANT ALL ON FUNCTION "public"."log_super_id_changes"() TO "anon";
GRANT ALL ON FUNCTION "public"."log_super_id_changes"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."log_super_id_changes"() TO "service_role";


















GRANT ALL ON TABLE "public"."alembic_version" TO "anon";
GRANT ALL ON TABLE "public"."alembic_version" TO "authenticated";
GRANT ALL ON TABLE "public"."alembic_version" TO "service_role";



GRANT ALL ON TABLE "public"."generated_super_ids" TO "anon";
GRANT ALL ON TABLE "public"."generated_super_ids" TO "authenticated";
GRANT ALL ON TABLE "public"."generated_super_ids" TO "service_role";



GRANT ALL ON SEQUENCE "public"."generated_super_ids_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."generated_super_ids_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."generated_super_ids_id_seq" TO "service_role";









ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "service_role";






























RESET ALL;

