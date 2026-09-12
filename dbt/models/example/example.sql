{{ config(materialized='view') }}

select
    1 as example_id,
    'dbt-bigquery' as adapter_name
