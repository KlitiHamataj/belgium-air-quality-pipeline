/*
    Staging model: IRCELINE air quality measurements
    - Deduplicate (same station + pollutant + timestamp)
    - Cast types
    - Filter out null/negative values
    - Standardize pollutant names
*/

with source as (
    select * from read_parquet('../data/raw/irceline/*.parquet')
),

cleaned as (
    select
        station_id,
        station_label,
        latitude,
        longitude,
        -- Standardize pollutant names
        case
            when lower(pollutant) like '%particulate%2.5%' or lower(pollutant) like '%pm2%'
                then 'PM2.5'
            when lower(pollutant) like '%particulate%10%' or lower(pollutant) like '%pm10%'
                then 'PM10'
            when lower(pollutant) like '%no2%' or lower(pollutant) like '%nitrogen dioxide%'
                then 'NO2'
            when lower(pollutant) like '%o3%' or lower(pollutant) like '%ozone%'
                then 'O3'
            when lower(pollutant) like '%so2%'
                then 'SO2'
            when lower(pollutant) like '%co%' and lower(pollutant) not like '%cover%'
                then 'CO'
            when lower(pollutant) like '%bc%' or lower(pollutant) like '%black carbon%'
                then 'BC'
            else upper(trim(pollutant))
        end as pollutant,
        timestamp as measured_at,
        value as measurement_value,
        unit,
        ingested_at,
        'irceline' as data_source,

        -- Dedup: keep latest ingestion per measurement
        row_number() over (
            partition by station_id, pollutant, timestamp
            order by ingested_at desc
        ) as _row_num

    from source
    where
        value is not null
        and value >= 0          -- Negative concentrations are sensor errors
        and value < 1000        -- Cap obvious outliers (µg/m³)
        and latitude is not null
        and longitude is not null
)

select
    station_id,
    station_label,
    latitude,
    longitude,
    pollutant,
    measured_at,
    measurement_value,
    unit,
    ingested_at,
    data_source
from cleaned
where _row_num = 1
