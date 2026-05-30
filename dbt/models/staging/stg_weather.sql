/*
    Staging model: Open-Meteo weather data
    - Clean and type-cast
    - Add date/hour columns for easier joins
*/

with source as (
    select * from read_parquet('../data/raw/weather/*.parquet')
),

cleaned as (
    select
        location_name,
        latitude,
        longitude,
        timestamp as measured_at,
        cast(timestamp as date) as measured_date,
        extract(hour from timestamp) as measured_hour,
        temperature_2m,
        relative_humidity_2m,
        wind_speed_10m,
        wind_direction_10m,
        precipitation,
        pressure_msl,
        cloud_cover,
        boundary_layer_height,  -- Low BLH = pollution trapped near surface
        ingested_at,

        row_number() over (
            partition by location_name, timestamp
            order by ingested_at desc
        ) as _row_num

    from source
    where timestamp is not null
)

select
    location_name,
    latitude,
    longitude,
    measured_at,
    measured_date,
    measured_hour,
    temperature_2m,
    relative_humidity_2m,
    wind_speed_10m,
    wind_direction_10m,
    precipitation,
    pressure_msl,
    cloud_cover,
    boundary_layer_height,
    ingested_at
from cleaned
where _row_num = 1
