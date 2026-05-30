/*
    Intermediate: Join air quality measurements with nearest weather data.

    Strategy: For each air quality measurement, find the closest weather point
    (by lat/lon) at the same hour. This gives us weather context for every
    pollution reading without requiring exact co-location.
*/

with air_quality as (
    -- Union both sources into one stream
    select * from {{ ref('stg_irceline') }}
),

weather as (
    select * from {{ ref('stg_weather') }}
),

-- Find nearest weather station for each AQ station
-- Using simple Euclidean distance on lat/lon (good enough for Belgium's small area)
aq_with_weather as (
    select
        aq.station_id,
        aq.station_label,
        aq.latitude as station_lat,
        aq.longitude as station_lon,
        aq.pollutant,
        aq.measured_at,
        aq.measurement_value,
        aq.unit,
        aq.data_source,
        w.location_name as weather_station,
        w.temperature_2m,
        w.relative_humidity_2m,
        w.wind_speed_10m,
        w.wind_direction_10m,
        w.precipitation,
        w.pressure_msl,
        w.cloud_cover,
        w.boundary_layer_height,

        -- Rank weather stations by proximity
        row_number() over (
            partition by aq.station_id, aq.pollutant, aq.measured_at
            order by
                pow(aq.latitude - w.latitude, 2) +
                pow(aq.longitude - w.longitude, 2) asc
        ) as _weather_rank

    from air_quality aq
    left join weather w
        on date_trunc('hour', aq.measured_at) = date_trunc('hour', w.measured_at)
)

select
    station_id,
    station_label,
    station_lat,
    station_lon,
    pollutant,
    measured_at,
    measurement_value,
    unit,
    data_source,
    weather_station,
    temperature_2m,
    relative_humidity_2m,
    wind_speed_10m,
    wind_direction_10m,
    precipitation,
    pressure_msl,
    cloud_cover,
    boundary_layer_height
from aq_with_weather
where _weather_rank = 1
