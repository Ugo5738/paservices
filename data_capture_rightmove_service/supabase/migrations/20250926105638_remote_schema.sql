

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



CREATE SCHEMA IF NOT EXISTS "rightmove";


ALTER SCHEMA "rightmove" OWNER TO "postgres";


CREATE EXTENSION IF NOT EXISTS "pg_graphql" WITH SCHEMA "graphql";






CREATE EXTENSION IF NOT EXISTS "pg_stat_statements" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgcrypto" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "supabase_vault" WITH SCHEMA "vault";






CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA "extensions";






CREATE TYPE "public"."scrapeeventtypeenum" AS ENUM (
    'REQUEST_RECEIVED',
    'API_CALL_ATTEMPT',
    'API_CALL_SUCCESS',
    'API_CALL_FAILURE',
    'DATA_PARSED_SUCCESS',
    'DATA_PARSED_FAILURE',
    'DATA_STORED_SUCCESS',
    'DATA_STORED_FAILURE'
);


ALTER TYPE "public"."scrapeeventtypeenum" OWNER TO "postgres";

SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "public"."alembic_version" (
    "version_num" character varying(32) NOT NULL
);


ALTER TABLE "public"."alembic_version" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "rightmove"."api_properties_details_v2" (
    "snapshot_id" bigint NOT NULL,
    "id" bigint NOT NULL,
    "transaction_type" character varying(50),
    "channel" character varying(50),
    "bedrooms" integer,
    "bathrooms" integer,
    "address" "text",
    "contact_method" character varying(50),
    "property_disclaimer" "text",
    "property_phrase" character varying(255),
    "full_description" "text",
    "listing_update_reason" character varying(255),
    "property_url" "text",
    "school_checker_url" "text",
    "lettings_info" "jsonb",
    "property_display_type" character varying(100),
    "telephone_number" character varying(50),
    "saved" boolean,
    "sold_prices_url" "text",
    "market_info_url" "text",
    "note" "text",
    "link_to_glossary" "text",
    "enquired_timestamp" timestamp with time zone,
    "key_features" "text"[],
    "tags" "text"[],
    "virtual_tours" "jsonb",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_properties_details_v2" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "rightmove"."api_properties_details_v2_analytics_info" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "branch_id" character varying(50),
    "property_id" character varying(50),
    "online_viewing" character varying(10),
    "image_count" character varying(10),
    "floorplan_count" character varying(10),
    "beds" character varying(10),
    "postcode" character varying(20),
    "property_type" character varying(100),
    "property_sub_type" character varying(100),
    "added" character varying(20),
    "price" character varying(50),
    "tenure" character varying(100),
    "bathrooms" character varying(10),
    "shared_ownership" character varying(10),
    "electricity" character varying(50),
    "broadband" character varying(50),
    "water" character varying(50),
    "sewerage" character varying(50),
    "heating" character varying(50),
    "accessibility" character varying(50),
    "parking" character varying(50),
    "garden" character varying(50),
    "flood_history" character varying(50),
    "flood_defences" character varying(50),
    "flood_risk" character varying(50),
    "listed" character varying(50),
    "restrictions" character varying(50),
    "private_access" character varying(50),
    "public_access" character varying(50),
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_properties_details_v2_analytics_info" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_properties_details_v2_analytics_info_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_properties_details_v2_analytics_info_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_properties_details_v2_analytics_info_id_seq" OWNED BY "rightmove"."api_properties_details_v2_analytics_info"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_properties_details_v2_branch" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "identifier" integer,
    "name" character varying(255),
    "brand_name" character varying(255),
    "display_name" character varying(255),
    "address" "text",
    "logo" "text",
    "developer" boolean,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_properties_details_v2_branch" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_properties_details_v2_branch_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_properties_details_v2_branch_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_properties_details_v2_branch_id_seq" OWNED BY "rightmove"."api_properties_details_v2_branch"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_properties_details_v2_brochure" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "title" character varying(255),
    "show_brochure_lead" boolean,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_properties_details_v2_brochure" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_properties_details_v2_brochure_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_properties_details_v2_brochure_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_properties_details_v2_brochure_id_seq" OWNED BY "rightmove"."api_properties_details_v2_brochure"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_properties_details_v2_brochure_items" (
    "id" integer NOT NULL,
    "brochure_id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "url" "text",
    "caption" character varying(255),
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_properties_details_v2_brochure_items" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_properties_details_v2_brochure_items_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_properties_details_v2_brochure_items_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_properties_details_v2_brochure_items_id_seq" OWNED BY "rightmove"."api_properties_details_v2_brochure_items"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_properties_details_v2_epcs" (
    "id" integer NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "url" "text",
    "caption" character varying(255),
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_properties_details_v2_epcs" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_properties_details_v2_epcs_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_properties_details_v2_epcs_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_properties_details_v2_epcs_id_seq" OWNED BY "rightmove"."api_properties_details_v2_epcs"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_properties_details_v2_feature_obligations" (
    "id" bigint NOT NULL,
    "feature_id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "listed" "jsonb",
    "restrictions" "jsonb",
    "private_access" "jsonb",
    "public_access" "jsonb",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_properties_details_v2_feature_obligations" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_properties_details_v2_feature_obligations_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_properties_details_v2_feature_obligations_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_properties_details_v2_feature_obligations_id_seq" OWNED BY "rightmove"."api_properties_details_v2_feature_obligations"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_properties_details_v2_feature_risks" (
    "id" bigint NOT NULL,
    "feature_id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "flood_history" "jsonb",
    "flood_defences" "jsonb",
    "flood_risk" "jsonb",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_properties_details_v2_feature_risks" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_properties_details_v2_feature_risks_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_properties_details_v2_feature_risks_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_properties_details_v2_feature_risks_id_seq" OWNED BY "rightmove"."api_properties_details_v2_feature_risks"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_properties_details_v2_features" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "electricity" "jsonb",
    "broadband" "jsonb",
    "water" "jsonb",
    "sewerage" "jsonb",
    "heating" "jsonb",
    "accessibility" "jsonb",
    "parking" "jsonb",
    "garden" "jsonb",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_properties_details_v2_features" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_properties_details_v2_features_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_properties_details_v2_features_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_properties_details_v2_features_id_seq" OWNED BY "rightmove"."api_properties_details_v2_features"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_properties_details_v2_floorplans" (
    "id" integer NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "url" "text",
    "thumbnail_url" "text",
    "caption" character varying(255),
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_properties_details_v2_floorplans" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_properties_details_v2_floorplans_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_properties_details_v2_floorplans_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_properties_details_v2_floorplans_id_seq" OWNED BY "rightmove"."api_properties_details_v2_floorplans"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_properties_details_v2_local_tax" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "type" character varying(100),
    "status" "text",
    "value" character varying(100),
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_properties_details_v2_local_tax" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_properties_details_v2_local_tax_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_properties_details_v2_local_tax_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_properties_details_v2_local_tax_id_seq" OWNED BY "rightmove"."api_properties_details_v2_local_tax"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_properties_details_v2_location" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "pin_type" character varying(100),
    "latitude" numeric(10,8),
    "longitude" numeric(11,8),
    "map_preview_url" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_properties_details_v2_location" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_properties_details_v2_location_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_properties_details_v2_location_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_properties_details_v2_location_id_seq" OWNED BY "rightmove"."api_properties_details_v2_location"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_properties_details_v2_location_street_view" (
    "id" bigint NOT NULL,
    "location_id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "latitude" numeric(10,8),
    "longitude" numeric(11,8),
    "heading" "text",
    "pitch" "text",
    "zoom" "text",
    "url" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_properties_details_v2_location_street_view" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_properties_details_v2_location_street_view_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_properties_details_v2_location_street_view_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_properties_details_v2_location_street_view_id_seq" OWNED BY "rightmove"."api_properties_details_v2_location_street_view"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_properties_details_v2_mis_info" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "branch_id" integer,
    "offer_advert_stamp_type_id" "text",
    "brand_plus" boolean,
    "featured_property" boolean,
    "channel" character varying(50),
    "premium_display" boolean,
    "premium_display_stamp_id" "text",
    "country_code" character varying(10),
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_properties_details_v2_mis_info" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_properties_details_v2_mis_info_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_properties_details_v2_mis_info_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_properties_details_v2_mis_info_id_seq" OWNED BY "rightmove"."api_properties_details_v2_mis_info"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_properties_details_v2_mortgage" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "price" bigint,
    "property_type_alias" character varying(100),
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_properties_details_v2_mortgage" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_properties_details_v2_mortgage_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_properties_details_v2_mortgage_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_properties_details_v2_mortgage_id_seq" OWNED BY "rightmove"."api_properties_details_v2_mortgage"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_properties_details_v2_photos" (
    "id" integer NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "url" "text",
    "thumbnail_url" "text",
    "max_size_url" "text",
    "caption" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_properties_details_v2_photos" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_properties_details_v2_photos_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_properties_details_v2_photos_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_properties_details_v2_photos_id_seq" OWNED BY "rightmove"."api_properties_details_v2_photos"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_properties_details_v2_price" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "primary_price" character varying(100),
    "secondary_price" character varying(255),
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_properties_details_v2_price" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_properties_details_v2_price_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_properties_details_v2_price_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_properties_details_v2_price_id_seq" OWNED BY "rightmove"."api_properties_details_v2_price"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_properties_details_v2_sales_info" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "tenure_type" character varying(100),
    "tenure_display_type" character varying(100),
    "ground_rent" "text",
    "annual_service_charge" "text",
    "estate_charge" "text",
    "length_of_lease" "text",
    "shared_ownership_percentage" "text",
    "shared_ownership_rent" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_properties_details_v2_sales_info" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_properties_details_v2_sales_info_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_properties_details_v2_sales_info_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_properties_details_v2_sales_info_id_seq" OWNED BY "rightmove"."api_properties_details_v2_sales_info"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_properties_details_v2_size" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "primary_size" character varying(100),
    "secondary_size" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_properties_details_v2_size" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_properties_details_v2_size_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_properties_details_v2_size_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_properties_details_v2_size_id_seq" OWNED BY "rightmove"."api_properties_details_v2_size"."id";



CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_properties_details_v2_snapshot_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_properties_details_v2_snapshot_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_properties_details_v2_snapshot_id_seq" OWNED BY "rightmove"."api_properties_details_v2"."snapshot_id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_properties_details_v2_stamp_duty" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "country" character varying(100),
    "price" bigint,
    "buyer_type" "text",
    "result" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_properties_details_v2_stamp_duty" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_properties_details_v2_stamp_duty_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_properties_details_v2_stamp_duty_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_properties_details_v2_stamp_duty_id_seq" OWNED BY "rightmove"."api_properties_details_v2_stamp_duty"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_properties_details_v2_stations" (
    "id" integer NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "station" character varying(255),
    "distance" numeric(8,2),
    "type" character varying(50),
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_properties_details_v2_stations" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_properties_details_v2_stations_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_properties_details_v2_stations_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_properties_details_v2_stations_id_seq" OWNED BY "rightmove"."api_properties_details_v2_stations"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_properties_details_v2_status" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "available" boolean,
    "label" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_properties_details_v2_status" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_properties_details_v2_status_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_properties_details_v2_status_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_properties_details_v2_status_id_seq" OWNED BY "rightmove"."api_properties_details_v2_status"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_addresses" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "country_code" character varying(10),
    "delivery_point_id" bigint,
    "display_address" "text",
    "incode" character varying(10),
    "outcode" character varying(10),
    "uk_country" character varying(100),
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_addresses" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_addresses_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_addresses_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_addresses_id_seq" OWNED BY "rightmove"."api_property_detail_addresses"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_broadbands" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "broadband_checker_url" "text",
    "disclaimer" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_broadbands" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_broadbands_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_broadbands_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_broadbands_id_seq" OWNED BY "rightmove"."api_property_detail_broadbands"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_contact_info_telephone_numbers" (
    "id" bigint NOT NULL,
    "contact_info_id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "disclaimer_description" "text",
    "disclaimer_text" "text",
    "disclaimer_title" "text",
    "international_number" character varying(50),
    "local_number" character varying(50),
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_contact_info_telephone_numbers" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_contact_info_telephone_numbers_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_contact_info_telephone_numbers_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_contact_info_telephone_numbers_id_seq" OWNED BY "rightmove"."api_property_detail_contact_info_telephone_numbers"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_contact_infos" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "contact_method" character varying(100),
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_contact_infos" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_contact_infos_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_contact_infos_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_contact_infos_id_seq" OWNED BY "rightmove"."api_property_detail_contact_infos"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_customer_descriptions" (
    "id" bigint NOT NULL,
    "customer_id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "is_truncated" boolean,
    "truncated_description_html" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_customer_descriptions" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_customer_descriptions_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_customer_descriptions_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_customer_descriptions_id_seq" OWNED BY "rightmove"."api_property_detail_customer_descriptions"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_customer_development_infos" (
    "id" bigint NOT NULL,
    "customer_id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "site_plan_uri" "text",
    "microsite_features" "text"[],
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_customer_development_infos" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_customer_development_infos_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_customer_development_infos_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_customer_development_infos_id_seq" OWNED BY "rightmove"."api_property_detail_customer_development_infos"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_customer_products" (
    "id" bigint NOT NULL,
    "customer_id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "has_microsite" boolean,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_customer_products" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_customer_products_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_customer_products_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_customer_products_id_seq" OWNED BY "rightmove"."api_property_detail_customer_products"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_customers" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "banner_ad" "text",
    "branch_display_name" character varying(255),
    "branch_id" integer,
    "branch_name" character varying(255),
    "build_to_rent" boolean,
    "build_to_rent_benefits" "text"[],
    "commercial" boolean,
    "company_name" character varying(255),
    "company_trading_name" character varying(255),
    "customer_banner_ad_profile_url" "text",
    "customer_mpu_ad_profile_url" "text",
    "customer_profile_url" "text",
    "customer_properties_url" "text",
    "display_address" "text",
    "is_new_home_developer" boolean,
    "logo_path" "text",
    "mpu_ad" "text",
    "show_brochure_lead_modal" boolean,
    "spotlight" "text",
    "valuation_form_url" "text",
    "video_enabled" boolean,
    "video_url" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_customers" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_customers_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_customers_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_customers_id_seq" OWNED BY "rightmove"."api_property_detail_customers"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_dfp_ad_infos" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "channel" character varying(50),
    "targeting" "jsonb",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_dfp_ad_infos" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_dfp_ad_infos_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_dfp_ad_infos_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_dfp_ad_infos_id_seq" OWNED BY "rightmove"."api_property_detail_dfp_ad_infos"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_floorplan_resized_floorplan_urls" (
    "id" bigint NOT NULL,
    "floorplan_id" integer NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "size_296x197" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_floorplan_resized_floorplan_urls" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_floorplan_resized_floorplan_urls_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_floorplan_resized_floorplan_urls_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_floorplan_resized_floorplan_urls_id_seq" OWNED BY "rightmove"."api_property_detail_floorplan_resized_floorplan_urls"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_floorplans" (
    "id" integer NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "caption" character varying(255),
    "type" character varying(50),
    "url" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_floorplans" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_floorplans_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_floorplans_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_floorplans_id_seq" OWNED BY "rightmove"."api_property_detail_floorplans"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_image_resized_image_urls" (
    "id" bigint NOT NULL,
    "image_id" integer NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "size_135x100" "text",
    "size_476x317" "text",
    "size_656x437" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_image_resized_image_urls" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_image_resized_image_urls_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_image_resized_image_urls_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_image_resized_image_urls_id_seq" OWNED BY "rightmove"."api_property_detail_image_resized_image_urls"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_images" (
    "id" integer NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "caption" character varying(255),
    "url" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_images" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_images_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_images_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_images_id_seq" OWNED BY "rightmove"."api_property_detail_images"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_industry_affiliations" (
    "id" integer NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "image_path" "text",
    "name" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_industry_affiliations" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_industry_affiliations_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_industry_affiliations_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_industry_affiliations_id_seq" OWNED BY "rightmove"."api_property_detail_industry_affiliations"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_info_reel_items" (
    "id" integer NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "primary_text" "text",
    "secondary_text" "text",
    "title" "text",
    "tooltip_text" "text",
    "type" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_info_reel_items" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_info_reel_items_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_info_reel_items_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_info_reel_items_id_seq" OWNED BY "rightmove"."api_property_detail_info_reel_items"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_listing_history" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "listing_update_reason" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_listing_history" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_listing_history_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_listing_history_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_listing_history_id_seq" OWNED BY "rightmove"."api_property_detail_listing_history"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_living_costs" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "annual_ground_rent" "text",
    "annual_service_charge" "text",
    "council_tax_band" character varying(10),
    "council_tax_exempt" boolean,
    "council_tax_included" boolean,
    "domestic_rates" "text",
    "ground_rent_percentage_increase" "text",
    "ground_rent_review_period_in_years" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_living_costs" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_living_costs_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_living_costs_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_living_costs_id_seq" OWNED BY "rightmove"."api_property_detail_living_costs"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_locations" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "circle_radius_on_map" integer,
    "latitude" numeric(10,8),
    "longitude" numeric(11,8),
    "pin_type" character varying(50),
    "show_map" boolean,
    "zoom_level" integer,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_locations" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_locations_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_locations_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_locations_id_seq" OWNED BY "rightmove"."api_property_detail_locations"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_mis_infos" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "branch_id" integer,
    "brand_plus" boolean,
    "featured_property" boolean,
    "offer_advert_stamp_type_id" "text",
    "premium_display" boolean,
    "premium_display_stamp_id" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_mis_infos" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_mis_infos_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_mis_infos_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_mis_infos_id_seq" OWNED BY "rightmove"."api_property_detail_mis_infos"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_mortgage_calculators" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "price" bigint,
    "property_type_alias" character varying(100),
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_mortgage_calculators" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_mortgage_calculators_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_mortgage_calculators_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_mortgage_calculators_id_seq" OWNED BY "rightmove"."api_property_detail_mortgage_calculators"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_nearest_station_types" (
    "id" integer NOT NULL,
    "station_id" integer NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "type" character varying(100),
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_nearest_station_types" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_nearest_station_types_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_nearest_station_types_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_nearest_station_types_id_seq" OWNED BY "rightmove"."api_property_detail_nearest_station_types"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_nearest_stations" (
    "id" integer NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "distance" numeric(18,16),
    "name" "text",
    "unit" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_nearest_stations" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_nearest_stations_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_nearest_stations_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_nearest_stations_id_seq" OWNED BY "rightmove"."api_property_detail_nearest_stations"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_prices" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "display_price_qualifier" character varying(255),
    "exchange_rate" "text",
    "message" "text",
    "price_per_sq_ft" character varying(100),
    "primary_price" character varying(100),
    "secondary_price" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_prices" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_prices_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_prices_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_prices_id_seq" OWNED BY "rightmove"."api_property_detail_prices"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_property_urls" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "nearby_sold_properties_url" "text",
    "similar_properties_url" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_property_urls" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_property_urls_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_property_urls_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_property_urls_id_seq" OWNED BY "rightmove"."api_property_detail_property_urls"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_shared_ownerships" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "ownership_percentage" numeric(10,4),
    "rent_frequency" character varying(100),
    "rent_price" numeric(12,2),
    "shared_ownership" boolean,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_shared_ownerships" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_shared_ownerships_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_shared_ownerships_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_shared_ownerships_id_seq" OWNED BY "rightmove"."api_property_detail_shared_ownerships"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_static_map_img_urls" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "static_map_img_url_desktop_large" "text",
    "static_map_img_url_desktop_small" "text",
    "static_map_img_url_mobile" "text",
    "static_map_img_url_tablet" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_static_map_img_urls" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_static_map_img_urls_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_static_map_img_urls_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_static_map_img_urls_id_seq" OWNED BY "rightmove"."api_property_detail_static_map_img_urls"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_status" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "archived" boolean,
    "published" boolean,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_status" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_status_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_status_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_status_id_seq" OWNED BY "rightmove"."api_property_detail_status"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_street_views" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "heading" "text",
    "latitude" numeric(10,8),
    "longitude" numeric(11,8),
    "pitch" "text",
    "zoom" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_street_views" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_street_views_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_street_views_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_street_views_id_seq" OWNED BY "rightmove"."api_property_detail_street_views"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_tenures" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "message" "text",
    "tenure_type" character varying(100),
    "years_remaining_on_lease" integer,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_tenures" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_tenures_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_tenures_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_tenures_id_seq" OWNED BY "rightmove"."api_property_detail_tenures"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_detail_texts" (
    "id" bigint NOT NULL,
    "api_property_snapshot_id" bigint NOT NULL,
    "api_property_id" bigint NOT NULL,
    "auction_fees_disclaimer" "text",
    "description" "text",
    "disclaimer" "text",
    "guide_price_disclaimer" "text",
    "new_homes_brochure_disclaimer" "text",
    "page_title" "text",
    "property_phrase" character varying(255),
    "reserve_price_disclaimer" "text",
    "share_description" "text",
    "share_text" "text",
    "short_description" "text",
    "static_map_disclaimer_text" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_detail_texts" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_detail_texts_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_detail_texts_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_detail_texts_id_seq" OWNED BY "rightmove"."api_property_detail_texts"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."api_property_details" (
    "snapshot_id" bigint NOT NULL,
    "id" bigint NOT NULL,
    "affordable_buying_scheme" boolean,
    "ai_location_info" "text",
    "bathrooms" integer,
    "bedrooms" integer,
    "business_for_sale" boolean,
    "channel" character varying(50),
    "commercial" boolean,
    "country_guide" "text",
    "enc_id" "text",
    "fees_apply" "jsonb",
    "lettings" "jsonb",
    "property_sub_type" "text",
    "show_school_info" boolean,
    "sold_property_type" character varying(100),
    "terms_of_use" "text",
    "transaction_type" character varying(50),
    "brochures" "jsonb",
    "commercial_use_classes" "text"[],
    "epc_graphs" "jsonb",
    "key_features" "text"[],
    "nearest_airports" "text"[],
    "rooms" "text"[],
    "sizings" "jsonb",
    "tags" "text"[],
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "super_id" "uuid" NOT NULL
);


ALTER TABLE "rightmove"."api_property_details" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."api_property_details_snapshot_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."api_property_details_snapshot_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."api_property_details_snapshot_id_seq" OWNED BY "rightmove"."api_property_details"."snapshot_id";



CREATE TABLE IF NOT EXISTS "rightmove"."property_display_prices" (
    "id" integer NOT NULL,
    "property_listing_snapshot_id" bigint NOT NULL,
    "super_id" "uuid" NOT NULL,
    "display_price" character varying(100),
    "display_price_qualifier" character varying(255),
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "rightmove"."property_display_prices" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."property_display_prices_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."property_display_prices_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."property_display_prices_id_seq" OWNED BY "rightmove"."property_display_prices"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."property_images" (
    "id" integer NOT NULL,
    "property_listing_snapshot_id" bigint NOT NULL,
    "super_id" "uuid" NOT NULL,
    "caption" character varying(255),
    "src_url" "text",
    "url" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "rightmove"."property_images" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."property_images_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."property_images_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."property_images_id_seq" OWNED BY "rightmove"."property_images"."id";



CREATE TABLE IF NOT EXISTS "rightmove"."property_listings" (
    "snapshot_id" bigint NOT NULL,
    "id" bigint NOT NULL,
    "super_id" "uuid" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "api_source_endpoint" character varying(100) NOT NULL,
    "added_or_reduced" character varying(255),
    "auction" boolean,
    "bathrooms" integer,
    "bedrooms" integer,
    "channel" character varying(50),
    "commercial" boolean,
    "contact_url" "text",
    "country_code" character varying(10),
    "development" boolean,
    "display_address" character varying(512),
    "display_size" character varying(100),
    "display_status" character varying(255),
    "distance" numeric(10,4),
    "enhanced_listing" boolean,
    "enquired_timestamp" timestamp without time zone,
    "featured_property" boolean,
    "fees_apply" boolean,
    "fees_apply_text" "text",
    "first_visible_date" timestamp without time zone,
    "formatted_branch_name" character varying(255),
    "formatted_distance" character varying(100),
    "has_brand_plus" boolean,
    "heading" "text",
    "hidden" boolean,
    "is_recent" boolean,
    "keyword_match_type" character varying(100),
    "keywords_json" "jsonb",
    "number_of_floorplans" integer,
    "number_of_images" integer,
    "number_of_virtual_tours" integer,
    "online_viewings_available" boolean,
    "premium_listing" boolean,
    "property_sub_type" character varying(100),
    "property_type_full_description" character varying(255),
    "property_url" "text",
    "residential" boolean,
    "saved" boolean,
    "show_on_map" boolean,
    "static_map_url" "text",
    "students" boolean,
    "summary" "text",
    "transaction_type" character varying(50),
    "customer_branch_display_name" character varying(255),
    "customer_branch_id" integer,
    "customer_branch_landing_page_url" "text",
    "customer_branch_name" character varying(255),
    "customer_brand_plus_logo_uri" "text",
    "customer_brand_plus_logo_url" "text",
    "customer_brand_trading_name" character varying(255),
    "customer_build_to_rent" boolean,
    "customer_build_to_rent_benefits_json" "jsonb",
    "customer_commercial" boolean,
    "customer_contact_telephone" character varying(50),
    "customer_development" boolean,
    "customer_development_content" "text",
    "customer_enhanced_listing" boolean,
    "customer_show_on_map" boolean,
    "customer_show_reduced_properties" boolean,
    "listing_update_date" timestamp without time zone,
    "listing_update_reason" character varying(100),
    "location_latitude" numeric(10,8),
    "location_longitude" numeric(11,8),
    "lozenge_model_matching_lozenges_json" "jsonb",
    "price_amount" numeric(14,2),
    "price_currency_code" character varying(10),
    "price_frequency" character varying(50),
    "product_label_text" character varying(255),
    "product_label_spotlight_label" boolean,
    "property_images_main_image_src" "text",
    "property_images_main_map_image_src" "text"
);


ALTER TABLE "rightmove"."property_listings" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."property_listings_snapshot_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."property_listings_snapshot_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."property_listings_snapshot_id_seq" OWNED BY "rightmove"."property_listings"."snapshot_id";



CREATE TABLE IF NOT EXISTS "rightmove"."scrape_events" (
    "id" bigint NOT NULL,
    "super_id" "uuid" NOT NULL,
    "rightmove_property_id" bigint,
    "event_type" "public"."scrapeeventtypeenum" NOT NULL,
    "event_timestamp" timestamp with time zone DEFAULT "now"() NOT NULL,
    "source_service_name" "text",
    "api_endpoint_called" "text",
    "http_status_code" integer,
    "error_code" "text",
    "error_message" "text",
    "payload" "jsonb",
    "response_item_count" integer,
    "response_null_item_count" integer,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "rightmove"."scrape_events" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "rightmove"."scrape_events_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "rightmove"."scrape_events_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "rightmove"."scrape_events_id_seq" OWNED BY "rightmove"."scrape_events"."id";



ALTER TABLE ONLY "rightmove"."api_properties_details_v2" ALTER COLUMN "snapshot_id" SET DEFAULT "nextval"('"rightmove"."api_properties_details_v2_snapshot_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_analytics_info" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_properties_details_v2_analytics_info_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_branch" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_properties_details_v2_branch_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_brochure" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_properties_details_v2_brochure_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_brochure_items" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_properties_details_v2_brochure_items_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_epcs" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_properties_details_v2_epcs_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_feature_obligations" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_properties_details_v2_feature_obligations_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_feature_risks" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_properties_details_v2_feature_risks_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_features" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_properties_details_v2_features_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_floorplans" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_properties_details_v2_floorplans_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_local_tax" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_properties_details_v2_local_tax_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_location" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_properties_details_v2_location_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_location_street_view" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_properties_details_v2_location_street_view_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_mis_info" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_properties_details_v2_mis_info_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_mortgage" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_properties_details_v2_mortgage_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_photos" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_properties_details_v2_photos_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_price" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_properties_details_v2_price_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_sales_info" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_properties_details_v2_sales_info_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_size" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_properties_details_v2_size_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_stamp_duty" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_properties_details_v2_stamp_duty_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_stations" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_properties_details_v2_stations_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_status" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_properties_details_v2_status_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_addresses" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_addresses_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_broadbands" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_broadbands_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_contact_info_telephone_numbers" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_contact_info_telephone_numbers_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_contact_infos" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_contact_infos_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_customer_descriptions" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_customer_descriptions_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_customer_development_infos" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_customer_development_infos_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_customer_products" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_customer_products_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_customers" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_customers_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_dfp_ad_infos" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_dfp_ad_infos_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_floorplan_resized_floorplan_urls" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_floorplan_resized_floorplan_urls_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_floorplans" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_floorplans_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_image_resized_image_urls" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_image_resized_image_urls_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_images" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_images_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_industry_affiliations" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_industry_affiliations_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_info_reel_items" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_info_reel_items_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_listing_history" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_listing_history_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_living_costs" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_living_costs_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_locations" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_locations_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_mis_infos" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_mis_infos_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_mortgage_calculators" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_mortgage_calculators_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_nearest_station_types" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_nearest_station_types_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_nearest_stations" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_nearest_stations_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_prices" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_prices_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_property_urls" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_property_urls_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_shared_ownerships" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_shared_ownerships_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_static_map_img_urls" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_static_map_img_urls_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_status" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_status_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_street_views" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_street_views_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_tenures" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_tenures_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_detail_texts" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."api_property_detail_texts_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."api_property_details" ALTER COLUMN "snapshot_id" SET DEFAULT "nextval"('"rightmove"."api_property_details_snapshot_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."property_display_prices" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."property_display_prices_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."property_images" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."property_images_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."property_listings" ALTER COLUMN "snapshot_id" SET DEFAULT "nextval"('"rightmove"."property_listings_snapshot_id_seq"'::"regclass");



ALTER TABLE ONLY "rightmove"."scrape_events" ALTER COLUMN "id" SET DEFAULT "nextval"('"rightmove"."scrape_events_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."alembic_version"
    ADD CONSTRAINT "alembic_version_pkc" PRIMARY KEY ("version_num");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2"
    ADD CONSTRAINT "pk_api_properties_details_v2" PRIMARY KEY ("snapshot_id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_analytics_info"
    ADD CONSTRAINT "pk_api_properties_details_v2_analytics_info" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_branch"
    ADD CONSTRAINT "pk_api_properties_details_v2_branch" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_brochure"
    ADD CONSTRAINT "pk_api_properties_details_v2_brochure" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_brochure_items"
    ADD CONSTRAINT "pk_api_properties_details_v2_brochure_items" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_epcs"
    ADD CONSTRAINT "pk_api_properties_details_v2_epcs" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_feature_obligations"
    ADD CONSTRAINT "pk_api_properties_details_v2_feature_obligations" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_feature_risks"
    ADD CONSTRAINT "pk_api_properties_details_v2_feature_risks" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_features"
    ADD CONSTRAINT "pk_api_properties_details_v2_features" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_floorplans"
    ADD CONSTRAINT "pk_api_properties_details_v2_floorplans" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_local_tax"
    ADD CONSTRAINT "pk_api_properties_details_v2_local_tax" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_location"
    ADD CONSTRAINT "pk_api_properties_details_v2_location" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_location_street_view"
    ADD CONSTRAINT "pk_api_properties_details_v2_location_street_view" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_mis_info"
    ADD CONSTRAINT "pk_api_properties_details_v2_mis_info" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_mortgage"
    ADD CONSTRAINT "pk_api_properties_details_v2_mortgage" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_photos"
    ADD CONSTRAINT "pk_api_properties_details_v2_photos" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_price"
    ADD CONSTRAINT "pk_api_properties_details_v2_price" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_sales_info"
    ADD CONSTRAINT "pk_api_properties_details_v2_sales_info" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_size"
    ADD CONSTRAINT "pk_api_properties_details_v2_size" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_stamp_duty"
    ADD CONSTRAINT "pk_api_properties_details_v2_stamp_duty" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_stations"
    ADD CONSTRAINT "pk_api_properties_details_v2_stations" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_status"
    ADD CONSTRAINT "pk_api_properties_details_v2_status" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_addresses"
    ADD CONSTRAINT "pk_api_property_detail_addresses" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_broadbands"
    ADD CONSTRAINT "pk_api_property_detail_broadbands" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_contact_info_telephone_numbers"
    ADD CONSTRAINT "pk_api_property_detail_contact_info_telephone_numbers" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_contact_infos"
    ADD CONSTRAINT "pk_api_property_detail_contact_infos" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_customer_descriptions"
    ADD CONSTRAINT "pk_api_property_detail_customer_descriptions" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_customer_development_infos"
    ADD CONSTRAINT "pk_api_property_detail_customer_development_infos" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_customer_products"
    ADD CONSTRAINT "pk_api_property_detail_customer_products" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_customers"
    ADD CONSTRAINT "pk_api_property_detail_customers" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_dfp_ad_infos"
    ADD CONSTRAINT "pk_api_property_detail_dfp_ad_infos" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_floorplan_resized_floorplan_urls"
    ADD CONSTRAINT "pk_api_property_detail_floorplan_resized_floorplan_urls" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_floorplans"
    ADD CONSTRAINT "pk_api_property_detail_floorplans" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_image_resized_image_urls"
    ADD CONSTRAINT "pk_api_property_detail_image_resized_image_urls" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_images"
    ADD CONSTRAINT "pk_api_property_detail_images" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_industry_affiliations"
    ADD CONSTRAINT "pk_api_property_detail_industry_affiliations" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_info_reel_items"
    ADD CONSTRAINT "pk_api_property_detail_info_reel_items" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_listing_history"
    ADD CONSTRAINT "pk_api_property_detail_listing_history" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_living_costs"
    ADD CONSTRAINT "pk_api_property_detail_living_costs" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_locations"
    ADD CONSTRAINT "pk_api_property_detail_locations" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_mis_infos"
    ADD CONSTRAINT "pk_api_property_detail_mis_infos" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_mortgage_calculators"
    ADD CONSTRAINT "pk_api_property_detail_mortgage_calculators" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_nearest_station_types"
    ADD CONSTRAINT "pk_api_property_detail_nearest_station_types" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_nearest_stations"
    ADD CONSTRAINT "pk_api_property_detail_nearest_stations" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_prices"
    ADD CONSTRAINT "pk_api_property_detail_prices" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_property_urls"
    ADD CONSTRAINT "pk_api_property_detail_property_urls" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_shared_ownerships"
    ADD CONSTRAINT "pk_api_property_detail_shared_ownerships" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_static_map_img_urls"
    ADD CONSTRAINT "pk_api_property_detail_static_map_img_urls" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_status"
    ADD CONSTRAINT "pk_api_property_detail_status" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_street_views"
    ADD CONSTRAINT "pk_api_property_detail_street_views" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_tenures"
    ADD CONSTRAINT "pk_api_property_detail_tenures" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_detail_texts"
    ADD CONSTRAINT "pk_api_property_detail_texts" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."api_property_details"
    ADD CONSTRAINT "pk_api_property_details" PRIMARY KEY ("snapshot_id");



ALTER TABLE ONLY "rightmove"."scrape_events"
    ADD CONSTRAINT "pk_scrape_events" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."property_display_prices"
    ADD CONSTRAINT "property_display_prices_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."property_images"
    ADD CONSTRAINT "property_images_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "rightmove"."property_listings"
    ADD CONSTRAINT "property_listings_pkey" PRIMARY KEY ("snapshot_id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_analytics_info"
    ADD CONSTRAINT "uq_api_properties_details_v2_analytics_info_api_propert_a789" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_branch"
    ADD CONSTRAINT "uq_api_properties_details_v2_branch_api_property_snapshot_id" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_brochure"
    ADD CONSTRAINT "uq_api_properties_details_v2_brochure_api_property_snapshot_id" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_feature_obligations"
    ADD CONSTRAINT "uq_api_properties_details_v2_feature_obligations_feature_id" UNIQUE ("feature_id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_feature_risks"
    ADD CONSTRAINT "uq_api_properties_details_v2_feature_risks_feature_id" UNIQUE ("feature_id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_features"
    ADD CONSTRAINT "uq_api_properties_details_v2_features_api_property_snapshot_id" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_local_tax"
    ADD CONSTRAINT "uq_api_properties_details_v2_local_tax_api_property_snapshot_id" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_location"
    ADD CONSTRAINT "uq_api_properties_details_v2_location_api_property_snapshot_id" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_location_street_view"
    ADD CONSTRAINT "uq_api_properties_details_v2_location_street_view_location_id" UNIQUE ("location_id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_mis_info"
    ADD CONSTRAINT "uq_api_properties_details_v2_mis_info_api_property_snapshot_id" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_mortgage"
    ADD CONSTRAINT "uq_api_properties_details_v2_mortgage_api_property_snapshot_id" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_price"
    ADD CONSTRAINT "uq_api_properties_details_v2_price_api_property_snapshot_id" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_sales_info"
    ADD CONSTRAINT "uq_api_properties_details_v2_sales_info_api_property_sn_5db0" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_size"
    ADD CONSTRAINT "uq_api_properties_details_v2_size_api_property_snapshot_id" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_stamp_duty"
    ADD CONSTRAINT "uq_api_properties_details_v2_stamp_duty_api_property_sn_2277" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_status"
    ADD CONSTRAINT "uq_api_properties_details_v2_status_api_property_snapshot_id" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_property_detail_addresses"
    ADD CONSTRAINT "uq_api_property_detail_addresses_api_property_snapshot_id" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_property_detail_broadbands"
    ADD CONSTRAINT "uq_api_property_detail_broadbands_api_property_snapshot_id" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_property_detail_contact_info_telephone_numbers"
    ADD CONSTRAINT "uq_api_property_detail_contact_info_telephone_numbers_c_41b0" UNIQUE ("contact_info_id");



ALTER TABLE ONLY "rightmove"."api_property_detail_contact_infos"
    ADD CONSTRAINT "uq_api_property_detail_contact_infos_api_property_snapshot_id" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_property_detail_customer_descriptions"
    ADD CONSTRAINT "uq_api_property_detail_customer_descriptions_customer_id" UNIQUE ("customer_id");



ALTER TABLE ONLY "rightmove"."api_property_detail_customer_development_infos"
    ADD CONSTRAINT "uq_api_property_detail_customer_development_infos_customer_id" UNIQUE ("customer_id");



ALTER TABLE ONLY "rightmove"."api_property_detail_customer_products"
    ADD CONSTRAINT "uq_api_property_detail_customer_products_customer_id" UNIQUE ("customer_id");



ALTER TABLE ONLY "rightmove"."api_property_detail_customers"
    ADD CONSTRAINT "uq_api_property_detail_customers_api_property_snapshot_id" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_property_detail_dfp_ad_infos"
    ADD CONSTRAINT "uq_api_property_detail_dfp_ad_infos_api_property_snapshot_id" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_property_detail_floorplan_resized_floorplan_urls"
    ADD CONSTRAINT "uq_api_property_detail_floorplan_resized_floorplan_urls_bb01" UNIQUE ("floorplan_id");



ALTER TABLE ONLY "rightmove"."api_property_detail_image_resized_image_urls"
    ADD CONSTRAINT "uq_api_property_detail_image_resized_image_urls_image_id" UNIQUE ("image_id");



ALTER TABLE ONLY "rightmove"."api_property_detail_listing_history"
    ADD CONSTRAINT "uq_api_property_detail_listing_history_api_property_snapshot_id" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_property_detail_living_costs"
    ADD CONSTRAINT "uq_api_property_detail_living_costs_api_property_snapshot_id" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_property_detail_locations"
    ADD CONSTRAINT "uq_api_property_detail_locations_api_property_snapshot_id" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_property_detail_mis_infos"
    ADD CONSTRAINT "uq_api_property_detail_mis_infos_api_property_snapshot_id" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_property_detail_mortgage_calculators"
    ADD CONSTRAINT "uq_api_property_detail_mortgage_calculators_api_propert_e735" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_property_detail_prices"
    ADD CONSTRAINT "uq_api_property_detail_prices_api_property_snapshot_id" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_property_detail_property_urls"
    ADD CONSTRAINT "uq_api_property_detail_property_urls_api_property_snapshot_id" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_property_detail_shared_ownerships"
    ADD CONSTRAINT "uq_api_property_detail_shared_ownerships_api_property_s_d0b9" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_property_detail_static_map_img_urls"
    ADD CONSTRAINT "uq_api_property_detail_static_map_img_urls_api_property_52a8" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_property_detail_status"
    ADD CONSTRAINT "uq_api_property_detail_status_api_property_snapshot_id" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_property_detail_street_views"
    ADD CONSTRAINT "uq_api_property_detail_street_views_api_property_snapshot_id" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_property_detail_tenures"
    ADD CONSTRAINT "uq_api_property_detail_tenures_api_property_snapshot_id" UNIQUE ("api_property_snapshot_id");



ALTER TABLE ONLY "rightmove"."api_property_detail_texts"
    ADD CONSTRAINT "uq_api_property_detail_texts_api_property_snapshot_id" UNIQUE ("api_property_snapshot_id");



CREATE INDEX "idx_property_display_prices_snapshot_id" ON "rightmove"."property_display_prices" USING "btree" ("property_listing_snapshot_id");



CREATE INDEX "idx_property_display_prices_super_id" ON "rightmove"."property_display_prices" USING "btree" ("super_id");



CREATE INDEX "idx_property_images_snapshot_id" ON "rightmove"."property_images" USING "btree" ("property_listing_snapshot_id");



CREATE INDEX "idx_property_images_super_id" ON "rightmove"."property_images" USING "btree" ("super_id");



CREATE INDEX "idx_property_listings_id" ON "rightmove"."property_listings" USING "btree" ("id");



CREATE INDEX "idx_property_listings_super_id" ON "rightmove"."property_listings" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_analytics_info_a_9ad5" ON "rightmove"."api_properties_details_v2_analytics_info" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_analytics_info_super_id" ON "rightmove"."api_properties_details_v2_analytics_info" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_branch_api_property_id" ON "rightmove"."api_properties_details_v2_branch" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_branch_super_id" ON "rightmove"."api_properties_details_v2_branch" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_brochure_api_property_id" ON "rightmove"."api_properties_details_v2_brochure" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_brochure_items_a_44de" ON "rightmove"."api_properties_details_v2_brochure_items" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_brochure_items_a_e69e" ON "rightmove"."api_properties_details_v2_brochure_items" USING "btree" ("api_property_snapshot_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_brochure_items_super_id" ON "rightmove"."api_properties_details_v2_brochure_items" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_brochure_super_id" ON "rightmove"."api_properties_details_v2_brochure" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_epcs_api_property_id" ON "rightmove"."api_properties_details_v2_epcs" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_epcs_super_id" ON "rightmove"."api_properties_details_v2_epcs" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_feature_obligati_c343" ON "rightmove"."api_properties_details_v2_feature_obligations" USING "btree" ("api_property_snapshot_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_feature_obligati_d4b8" ON "rightmove"."api_properties_details_v2_feature_obligations" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_feature_obligati_ff94" ON "rightmove"."api_properties_details_v2_feature_obligations" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_feature_risks_ap_7258" ON "rightmove"."api_properties_details_v2_feature_risks" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_feature_risks_ap_e092" ON "rightmove"."api_properties_details_v2_feature_risks" USING "btree" ("api_property_snapshot_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_feature_risks_super_id" ON "rightmove"."api_properties_details_v2_feature_risks" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_features_api_property_id" ON "rightmove"."api_properties_details_v2_features" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_features_super_id" ON "rightmove"."api_properties_details_v2_features" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_floorplans_api_p_9694" ON "rightmove"."api_properties_details_v2_floorplans" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_floorplans_super_id" ON "rightmove"."api_properties_details_v2_floorplans" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_id" ON "rightmove"."api_properties_details_v2" USING "btree" ("id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_local_tax_api_pr_8f0f" ON "rightmove"."api_properties_details_v2_local_tax" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_local_tax_super_id" ON "rightmove"."api_properties_details_v2_local_tax" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_location_api_property_id" ON "rightmove"."api_properties_details_v2_location" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_location_street__214d" ON "rightmove"."api_properties_details_v2_location_street_view" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_location_street__5c9e" ON "rightmove"."api_properties_details_v2_location_street_view" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_location_street__7062" ON "rightmove"."api_properties_details_v2_location_street_view" USING "btree" ("api_property_snapshot_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_location_super_id" ON "rightmove"."api_properties_details_v2_location" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_mis_info_api_property_id" ON "rightmove"."api_properties_details_v2_mis_info" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_mis_info_super_id" ON "rightmove"."api_properties_details_v2_mis_info" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_mortgage_api_property_id" ON "rightmove"."api_properties_details_v2_mortgage" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_mortgage_super_id" ON "rightmove"."api_properties_details_v2_mortgage" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_photos_api_property_id" ON "rightmove"."api_properties_details_v2_photos" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_photos_super_id" ON "rightmove"."api_properties_details_v2_photos" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_price_api_property_id" ON "rightmove"."api_properties_details_v2_price" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_price_super_id" ON "rightmove"."api_properties_details_v2_price" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_sales_info_api_p_2ca1" ON "rightmove"."api_properties_details_v2_sales_info" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_sales_info_super_id" ON "rightmove"."api_properties_details_v2_sales_info" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_size_api_property_id" ON "rightmove"."api_properties_details_v2_size" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_size_super_id" ON "rightmove"."api_properties_details_v2_size" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_stamp_duty_api_p_68b4" ON "rightmove"."api_properties_details_v2_stamp_duty" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_stamp_duty_super_id" ON "rightmove"."api_properties_details_v2_stamp_duty" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_stations_api_property_id" ON "rightmove"."api_properties_details_v2_stations" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_stations_super_id" ON "rightmove"."api_properties_details_v2_stations" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_status_api_property_id" ON "rightmove"."api_properties_details_v2_status" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_status_super_id" ON "rightmove"."api_properties_details_v2_status" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_properties_details_v2_super_id" ON "rightmove"."api_properties_details_v2" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_addresses_api_property_id" ON "rightmove"."api_property_detail_addresses" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_addresses_super_id" ON "rightmove"."api_property_detail_addresses" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_broadbands_api_property_id" ON "rightmove"."api_property_detail_broadbands" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_broadbands_super_id" ON "rightmove"."api_property_detail_broadbands" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_contact_info_telephone_2767" ON "rightmove"."api_property_detail_contact_info_telephone_numbers" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_contact_info_telephone_d048" ON "rightmove"."api_property_detail_contact_info_telephone_numbers" USING "btree" ("api_property_snapshot_id");



CREATE INDEX "ix_rightmove_api_property_detail_contact_info_telephone_d933" ON "rightmove"."api_property_detail_contact_info_telephone_numbers" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_contact_infos_api_property_id" ON "rightmove"."api_property_detail_contact_infos" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_contact_infos_super_id" ON "rightmove"."api_property_detail_contact_infos" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_customer_descriptions__63cd" ON "rightmove"."api_property_detail_customer_descriptions" USING "btree" ("api_property_snapshot_id");



CREATE INDEX "ix_rightmove_api_property_detail_customer_descriptions__a116" ON "rightmove"."api_property_detail_customer_descriptions" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_customer_descriptions_super_id" ON "rightmove"."api_property_detail_customer_descriptions" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_customer_development_i_52b8" ON "rightmove"."api_property_detail_customer_development_infos" USING "btree" ("api_property_snapshot_id");



CREATE INDEX "ix_rightmove_api_property_detail_customer_development_i_b4eb" ON "rightmove"."api_property_detail_customer_development_infos" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_customer_development_i_fbde" ON "rightmove"."api_property_detail_customer_development_infos" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_customer_products_api__8253" ON "rightmove"."api_property_detail_customer_products" USING "btree" ("api_property_snapshot_id");



CREATE INDEX "ix_rightmove_api_property_detail_customer_products_api__a6f9" ON "rightmove"."api_property_detail_customer_products" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_customer_products_super_id" ON "rightmove"."api_property_detail_customer_products" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_customers_api_property_id" ON "rightmove"."api_property_detail_customers" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_customers_super_id" ON "rightmove"."api_property_detail_customers" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_dfp_ad_infos_api_property_id" ON "rightmove"."api_property_detail_dfp_ad_infos" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_dfp_ad_infos_super_id" ON "rightmove"."api_property_detail_dfp_ad_infos" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_floorplan_resized_floo_0f93" ON "rightmove"."api_property_detail_floorplan_resized_floorplan_urls" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_floorplan_resized_floo_8404" ON "rightmove"."api_property_detail_floorplan_resized_floorplan_urls" USING "btree" ("api_property_snapshot_id");



CREATE INDEX "ix_rightmove_api_property_detail_floorplan_resized_floo_ee35" ON "rightmove"."api_property_detail_floorplan_resized_floorplan_urls" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_floorplans_api_property_id" ON "rightmove"."api_property_detail_floorplans" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_floorplans_super_id" ON "rightmove"."api_property_detail_floorplans" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_image_resized_image_ur_7718" ON "rightmove"."api_property_detail_image_resized_image_urls" USING "btree" ("api_property_snapshot_id");



CREATE INDEX "ix_rightmove_api_property_detail_image_resized_image_ur_a0da" ON "rightmove"."api_property_detail_image_resized_image_urls" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_image_resized_image_ur_c904" ON "rightmove"."api_property_detail_image_resized_image_urls" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_images_api_property_id" ON "rightmove"."api_property_detail_images" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_images_super_id" ON "rightmove"."api_property_detail_images" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_industry_affiliations__985c" ON "rightmove"."api_property_detail_industry_affiliations" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_industry_affiliations_super_id" ON "rightmove"."api_property_detail_industry_affiliations" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_info_reel_items_api_pr_22c2" ON "rightmove"."api_property_detail_info_reel_items" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_info_reel_items_super_id" ON "rightmove"."api_property_detail_info_reel_items" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_listing_history_api_pr_961c" ON "rightmove"."api_property_detail_listing_history" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_listing_history_super_id" ON "rightmove"."api_property_detail_listing_history" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_living_costs_api_property_id" ON "rightmove"."api_property_detail_living_costs" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_living_costs_super_id" ON "rightmove"."api_property_detail_living_costs" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_locations_api_property_id" ON "rightmove"."api_property_detail_locations" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_locations_super_id" ON "rightmove"."api_property_detail_locations" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_mis_infos_api_property_id" ON "rightmove"."api_property_detail_mis_infos" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_mis_infos_super_id" ON "rightmove"."api_property_detail_mis_infos" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_mortgage_calculators_a_4478" ON "rightmove"."api_property_detail_mortgage_calculators" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_mortgage_calculators_super_id" ON "rightmove"."api_property_detail_mortgage_calculators" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_nearest_station_types__41bd" ON "rightmove"."api_property_detail_nearest_station_types" USING "btree" ("api_property_snapshot_id");



CREATE INDEX "ix_rightmove_api_property_detail_nearest_station_types__56e0" ON "rightmove"."api_property_detail_nearest_station_types" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_nearest_station_types_super_id" ON "rightmove"."api_property_detail_nearest_station_types" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_nearest_stations_api_p_8cea" ON "rightmove"."api_property_detail_nearest_stations" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_nearest_stations_super_id" ON "rightmove"."api_property_detail_nearest_stations" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_prices_api_property_id" ON "rightmove"."api_property_detail_prices" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_prices_super_id" ON "rightmove"."api_property_detail_prices" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_property_urls_api_property_id" ON "rightmove"."api_property_detail_property_urls" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_property_urls_super_id" ON "rightmove"."api_property_detail_property_urls" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_shared_ownerships_api__0e58" ON "rightmove"."api_property_detail_shared_ownerships" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_shared_ownerships_super_id" ON "rightmove"."api_property_detail_shared_ownerships" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_static_map_img_urls_ap_c34a" ON "rightmove"."api_property_detail_static_map_img_urls" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_static_map_img_urls_super_id" ON "rightmove"."api_property_detail_static_map_img_urls" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_status_api_property_id" ON "rightmove"."api_property_detail_status" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_status_super_id" ON "rightmove"."api_property_detail_status" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_street_views_api_property_id" ON "rightmove"."api_property_detail_street_views" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_street_views_super_id" ON "rightmove"."api_property_detail_street_views" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_tenures_api_property_id" ON "rightmove"."api_property_detail_tenures" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_tenures_super_id" ON "rightmove"."api_property_detail_tenures" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_detail_texts_api_property_id" ON "rightmove"."api_property_detail_texts" USING "btree" ("api_property_id");



CREATE INDEX "ix_rightmove_api_property_detail_texts_super_id" ON "rightmove"."api_property_detail_texts" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_api_property_details_id" ON "rightmove"."api_property_details" USING "btree" ("id");



CREATE INDEX "ix_rightmove_api_property_details_super_id" ON "rightmove"."api_property_details" USING "btree" ("super_id");



CREATE INDEX "ix_rightmove_scrape_events_event_type" ON "rightmove"."scrape_events" USING "btree" ("event_type");



CREATE INDEX "ix_rightmove_scrape_events_rightmove_property_id" ON "rightmove"."scrape_events" USING "btree" ("rightmove_property_id");



CREATE INDEX "ix_rightmove_scrape_events_super_id" ON "rightmove"."scrape_events" USING "btree" ("super_id");



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_analytics_info"
    ADD CONSTRAINT "fk_api_properties_details_v2_analytics_info_api_propert_513f" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_properties_details_v2"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_branch"
    ADD CONSTRAINT "fk_api_properties_details_v2_branch_api_property_snapsh_cd57" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_properties_details_v2"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_brochure"
    ADD CONSTRAINT "fk_api_properties_details_v2_brochure_api_property_snap_09d8" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_properties_details_v2"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_brochure_items"
    ADD CONSTRAINT "fk_api_properties_details_v2_brochure_items_brochure_id_8d78" FOREIGN KEY ("brochure_id") REFERENCES "rightmove"."api_properties_details_v2_brochure"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_epcs"
    ADD CONSTRAINT "fk_api_properties_details_v2_epcs_api_property_snapshot_66e8" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_properties_details_v2"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_feature_obligations"
    ADD CONSTRAINT "fk_api_properties_details_v2_feature_obligations_featur_181d" FOREIGN KEY ("feature_id") REFERENCES "rightmove"."api_properties_details_v2_features"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_feature_risks"
    ADD CONSTRAINT "fk_api_properties_details_v2_feature_risks_feature_id_a_6810" FOREIGN KEY ("feature_id") REFERENCES "rightmove"."api_properties_details_v2_features"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_features"
    ADD CONSTRAINT "fk_api_properties_details_v2_features_api_property_snap_8b5f" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_properties_details_v2"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_floorplans"
    ADD CONSTRAINT "fk_api_properties_details_v2_floorplans_api_property_sn_2e02" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_properties_details_v2"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_local_tax"
    ADD CONSTRAINT "fk_api_properties_details_v2_local_tax_api_property_sna_d97b" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_properties_details_v2"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_location"
    ADD CONSTRAINT "fk_api_properties_details_v2_location_api_property_snap_4022" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_properties_details_v2"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_location_street_view"
    ADD CONSTRAINT "fk_api_properties_details_v2_location_street_view_locat_69cc" FOREIGN KEY ("location_id") REFERENCES "rightmove"."api_properties_details_v2_location"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_mis_info"
    ADD CONSTRAINT "fk_api_properties_details_v2_mis_info_api_property_snap_0139" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_properties_details_v2"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_mortgage"
    ADD CONSTRAINT "fk_api_properties_details_v2_mortgage_api_property_snap_d146" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_properties_details_v2"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_photos"
    ADD CONSTRAINT "fk_api_properties_details_v2_photos_api_property_snapsh_c0d0" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_properties_details_v2"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_price"
    ADD CONSTRAINT "fk_api_properties_details_v2_price_api_property_snapsho_7194" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_properties_details_v2"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_sales_info"
    ADD CONSTRAINT "fk_api_properties_details_v2_sales_info_api_property_sn_717d" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_properties_details_v2"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_size"
    ADD CONSTRAINT "fk_api_properties_details_v2_size_api_property_snapshot_88fb" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_properties_details_v2"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_stamp_duty"
    ADD CONSTRAINT "fk_api_properties_details_v2_stamp_duty_api_property_sn_9015" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_properties_details_v2"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_stations"
    ADD CONSTRAINT "fk_api_properties_details_v2_stations_api_property_snap_f6d8" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_properties_details_v2"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_properties_details_v2_status"
    ADD CONSTRAINT "fk_api_properties_details_v2_status_api_property_snapsh_3d36" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_properties_details_v2"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_addresses"
    ADD CONSTRAINT "fk_api_property_detail_addresses_api_property_snapshot__ceb3" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_property_details"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_broadbands"
    ADD CONSTRAINT "fk_api_property_detail_broadbands_api_property_snapshot_5d6b" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_property_details"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_contact_info_telephone_numbers"
    ADD CONSTRAINT "fk_api_property_detail_contact_info_telephone_numbers_c_0e44" FOREIGN KEY ("contact_info_id") REFERENCES "rightmove"."api_property_detail_contact_infos"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_contact_infos"
    ADD CONSTRAINT "fk_api_property_detail_contact_infos_api_property_snaps_528c" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_property_details"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_customer_descriptions"
    ADD CONSTRAINT "fk_api_property_detail_customer_descriptions_customer_i_ee79" FOREIGN KEY ("customer_id") REFERENCES "rightmove"."api_property_detail_customers"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_customer_development_infos"
    ADD CONSTRAINT "fk_api_property_detail_customer_development_infos_custo_fc30" FOREIGN KEY ("customer_id") REFERENCES "rightmove"."api_property_detail_customers"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_customer_products"
    ADD CONSTRAINT "fk_api_property_detail_customer_products_customer_id_ap_4226" FOREIGN KEY ("customer_id") REFERENCES "rightmove"."api_property_detail_customers"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_customers"
    ADD CONSTRAINT "fk_api_property_detail_customers_api_property_snapshot__5c0c" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_property_details"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_dfp_ad_infos"
    ADD CONSTRAINT "fk_api_property_detail_dfp_ad_infos_api_property_snapsh_0b7f" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_property_details"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_floorplan_resized_floorplan_urls"
    ADD CONSTRAINT "fk_api_property_detail_floorplan_resized_floorplan_urls_f230" FOREIGN KEY ("floorplan_id") REFERENCES "rightmove"."api_property_detail_floorplans"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_floorplans"
    ADD CONSTRAINT "fk_api_property_detail_floorplans_api_property_snapshot_a5f5" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_property_details"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_image_resized_image_urls"
    ADD CONSTRAINT "fk_api_property_detail_image_resized_image_urls_image_i_38d4" FOREIGN KEY ("image_id") REFERENCES "rightmove"."api_property_detail_images"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_images"
    ADD CONSTRAINT "fk_api_property_detail_images_api_property_snapshot_id__ce1d" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_property_details"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_industry_affiliations"
    ADD CONSTRAINT "fk_api_property_detail_industry_affiliations_api_proper_d202" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_property_details"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_info_reel_items"
    ADD CONSTRAINT "fk_api_property_detail_info_reel_items_api_property_sna_c711" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_property_details"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_listing_history"
    ADD CONSTRAINT "fk_api_property_detail_listing_history_api_property_sna_35b7" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_property_details"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_living_costs"
    ADD CONSTRAINT "fk_api_property_detail_living_costs_api_property_snapsh_454e" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_property_details"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_locations"
    ADD CONSTRAINT "fk_api_property_detail_locations_api_property_snapshot__abe4" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_property_details"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_mis_infos"
    ADD CONSTRAINT "fk_api_property_detail_mis_infos_api_property_snapshot__b5b7" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_property_details"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_mortgage_calculators"
    ADD CONSTRAINT "fk_api_property_detail_mortgage_calculators_api_propert_5f85" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_property_details"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_nearest_station_types"
    ADD CONSTRAINT "fk_api_property_detail_nearest_station_types_station_id_fec0" FOREIGN KEY ("station_id") REFERENCES "rightmove"."api_property_detail_nearest_stations"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_nearest_stations"
    ADD CONSTRAINT "fk_api_property_detail_nearest_stations_api_property_sn_0780" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_property_details"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_prices"
    ADD CONSTRAINT "fk_api_property_detail_prices_api_property_snapshot_id__803a" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_property_details"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_property_urls"
    ADD CONSTRAINT "fk_api_property_detail_property_urls_api_property_snaps_ce7a" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_property_details"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_shared_ownerships"
    ADD CONSTRAINT "fk_api_property_detail_shared_ownerships_api_property_s_9a39" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_property_details"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_static_map_img_urls"
    ADD CONSTRAINT "fk_api_property_detail_static_map_img_urls_api_property_cbb8" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_property_details"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_status"
    ADD CONSTRAINT "fk_api_property_detail_status_api_property_snapshot_id__e737" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_property_details"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_street_views"
    ADD CONSTRAINT "fk_api_property_detail_street_views_api_property_snapsh_b8b2" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_property_details"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_tenures"
    ADD CONSTRAINT "fk_api_property_detail_tenures_api_property_snapshot_id_1b00" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_property_details"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."api_property_detail_texts"
    ADD CONSTRAINT "fk_api_property_detail_texts_api_property_snapshot_id_a_fc7e" FOREIGN KEY ("api_property_snapshot_id") REFERENCES "rightmove"."api_property_details"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."property_display_prices"
    ADD CONSTRAINT "property_display_prices_property_listing_snapshot_id_fkey" FOREIGN KEY ("property_listing_snapshot_id") REFERENCES "rightmove"."property_listings"("snapshot_id") ON DELETE CASCADE;



ALTER TABLE ONLY "rightmove"."property_images"
    ADD CONSTRAINT "property_images_property_listing_snapshot_id_fkey" FOREIGN KEY ("property_listing_snapshot_id") REFERENCES "rightmove"."property_listings"("snapshot_id") ON DELETE CASCADE;





ALTER PUBLICATION "supabase_realtime" OWNER TO "postgres";


GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";








































































































































































GRANT ALL ON TABLE "public"."alembic_version" TO "anon";
GRANT ALL ON TABLE "public"."alembic_version" TO "authenticated";
GRANT ALL ON TABLE "public"."alembic_version" TO "service_role";









ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "service_role";






























RESET ALL;

