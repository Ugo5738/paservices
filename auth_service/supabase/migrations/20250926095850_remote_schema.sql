

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





SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "public"."alembic_version" (
    "version_num" character varying(32) NOT NULL
);


ALTER TABLE "public"."alembic_version" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."app_client_refresh_tokens" (
    "id" "uuid" NOT NULL,
    "app_client_id" "uuid" NOT NULL,
    "token_hash" character varying NOT NULL,
    "expires_at" timestamp with time zone NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "revoked_at" timestamp with time zone
);


ALTER TABLE "public"."app_client_refresh_tokens" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."app_client_roles" (
    "app_client_id" "uuid" NOT NULL,
    "role_id" "uuid" NOT NULL,
    "assigned_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."app_client_roles" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."app_clients" (
    "id" "uuid" NOT NULL,
    "client_name" character varying NOT NULL,
    "client_secret_hash" character varying NOT NULL,
    "is_active" boolean NOT NULL,
    "description" character varying,
    "allowed_callback_urls" character varying[],
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."app_clients" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."permissions" (
    "id" "uuid" NOT NULL,
    "name" character varying NOT NULL,
    "description" character varying,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."permissions" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."profiles" (
    "user_id" "uuid" NOT NULL,
    "email" character varying NOT NULL,
    "username" character varying,
    "first_name" character varying,
    "last_name" character varying,
    "is_active" boolean NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."profiles" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."role_permissions" (
    "role_id" "uuid" NOT NULL,
    "permission_id" "uuid" NOT NULL,
    "assigned_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."role_permissions" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."roles" (
    "id" "uuid" NOT NULL,
    "name" character varying NOT NULL,
    "description" character varying,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."roles" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."user_roles" (
    "user_id" "uuid" NOT NULL,
    "role_id" "uuid" NOT NULL,
    "assigned_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."user_roles" OWNER TO "postgres";


ALTER TABLE ONLY "public"."alembic_version"
    ADD CONSTRAINT "alembic_version_pkc" PRIMARY KEY ("version_num");



ALTER TABLE ONLY "public"."app_client_refresh_tokens"
    ADD CONSTRAINT "app_client_refresh_tokens_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."app_client_roles"
    ADD CONSTRAINT "app_client_roles_pkey" PRIMARY KEY ("app_client_id", "role_id");



ALTER TABLE ONLY "public"."app_clients"
    ADD CONSTRAINT "app_clients_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."permissions"
    ADD CONSTRAINT "permissions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."profiles"
    ADD CONSTRAINT "profiles_pkey" PRIMARY KEY ("user_id");



ALTER TABLE ONLY "public"."role_permissions"
    ADD CONSTRAINT "role_permissions_pkey" PRIMARY KEY ("role_id", "permission_id");



ALTER TABLE ONLY "public"."roles"
    ADD CONSTRAINT "roles_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."user_roles"
    ADD CONSTRAINT "user_roles_pkey" PRIMARY KEY ("user_id", "role_id");



CREATE INDEX "ix_app_client_refresh_tokens_app_client_id" ON "public"."app_client_refresh_tokens" USING "btree" ("app_client_id");



CREATE UNIQUE INDEX "ix_app_client_refresh_tokens_token_hash" ON "public"."app_client_refresh_tokens" USING "btree" ("token_hash");



CREATE UNIQUE INDEX "ix_app_clients_client_name" ON "public"."app_clients" USING "btree" ("client_name");



CREATE UNIQUE INDEX "ix_permissions_name" ON "public"."permissions" USING "btree" ("name");



CREATE INDEX "ix_profiles_email" ON "public"."profiles" USING "btree" ("email");



CREATE UNIQUE INDEX "ix_profiles_username" ON "public"."profiles" USING "btree" ("username");



CREATE UNIQUE INDEX "ix_roles_name" ON "public"."roles" USING "btree" ("name");



ALTER TABLE ONLY "public"."app_client_refresh_tokens"
    ADD CONSTRAINT "app_client_refresh_tokens_app_client_id_fkey" FOREIGN KEY ("app_client_id") REFERENCES "public"."app_clients"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."app_client_roles"
    ADD CONSTRAINT "app_client_roles_app_client_id_fkey" FOREIGN KEY ("app_client_id") REFERENCES "public"."app_clients"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."app_client_roles"
    ADD CONSTRAINT "app_client_roles_role_id_fkey" FOREIGN KEY ("role_id") REFERENCES "public"."roles"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."role_permissions"
    ADD CONSTRAINT "role_permissions_permission_id_fkey" FOREIGN KEY ("permission_id") REFERENCES "public"."permissions"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."role_permissions"
    ADD CONSTRAINT "role_permissions_role_id_fkey" FOREIGN KEY ("role_id") REFERENCES "public"."roles"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_roles"
    ADD CONSTRAINT "user_roles_role_id_fkey" FOREIGN KEY ("role_id") REFERENCES "public"."roles"("id") ON DELETE CASCADE;





ALTER PUBLICATION "supabase_realtime" OWNER TO "postgres";


GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";








































































































































































GRANT ALL ON TABLE "public"."alembic_version" TO "anon";
GRANT ALL ON TABLE "public"."alembic_version" TO "authenticated";
GRANT ALL ON TABLE "public"."alembic_version" TO "service_role";



GRANT ALL ON TABLE "public"."app_client_refresh_tokens" TO "anon";
GRANT ALL ON TABLE "public"."app_client_refresh_tokens" TO "authenticated";
GRANT ALL ON TABLE "public"."app_client_refresh_tokens" TO "service_role";



GRANT ALL ON TABLE "public"."app_client_roles" TO "anon";
GRANT ALL ON TABLE "public"."app_client_roles" TO "authenticated";
GRANT ALL ON TABLE "public"."app_client_roles" TO "service_role";



GRANT ALL ON TABLE "public"."app_clients" TO "anon";
GRANT ALL ON TABLE "public"."app_clients" TO "authenticated";
GRANT ALL ON TABLE "public"."app_clients" TO "service_role";



GRANT ALL ON TABLE "public"."permissions" TO "anon";
GRANT ALL ON TABLE "public"."permissions" TO "authenticated";
GRANT ALL ON TABLE "public"."permissions" TO "service_role";



GRANT ALL ON TABLE "public"."profiles" TO "anon";
GRANT ALL ON TABLE "public"."profiles" TO "authenticated";
GRANT ALL ON TABLE "public"."profiles" TO "service_role";



GRANT ALL ON TABLE "public"."role_permissions" TO "anon";
GRANT ALL ON TABLE "public"."role_permissions" TO "authenticated";
GRANT ALL ON TABLE "public"."role_permissions" TO "service_role";



GRANT ALL ON TABLE "public"."roles" TO "anon";
GRANT ALL ON TABLE "public"."roles" TO "authenticated";
GRANT ALL ON TABLE "public"."roles" TO "service_role";



GRANT ALL ON TABLE "public"."user_roles" TO "anon";
GRANT ALL ON TABLE "public"."user_roles" TO "authenticated";
GRANT ALL ON TABLE "public"."user_roles" TO "service_role";









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
